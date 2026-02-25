from zalo_bot import Update
from zalo_bot.ext import ContextTypes

from analytics.analyzer import analyze_query, get_quick_summary
from core.auth import get_user_by_zalo_id
from core.logger import logger
from core.router import Intent, detect_intent
from database.supabase import supabase
from forecasting.responder import answer_forecast, get_risk_alert
from knowledge.retriever import answer_question
from knowledge.source_manager import (
    add_source,
    remove_source,
    list_sources,
    resync_all_sources,
)
from support.feedback import submit_feedback, get_feedback_summary
from support.onboarding import (
    init_onboarding_zalo,
    get_current_step_content_zalo,
    advance_onboarding_zalo,
)
from support.drafter import draft_document
from support.task_helper import get_my_tasks, get_tasks_by_name
from platforms.zalo.formatter import strip_markdown


def _safe_handler(func):
    """Error wrapper for Zalo handlers (mirrors core/decorators.py safe_handler)."""
    import functools

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"Zalo error in {func.__name__}: {e}")
            if update and update.message:
                try:
                    await update.message.reply_text(
                        "Xin loi, toi gap loi. Vui long thu lai."
                    )
                except Exception:
                    pass

    return wrapper


def _get_zalo_user(update: Update) -> dict | None:
    """Look up user by Zalo ID."""
    zalo_id = str(update.effective_user.id)
    return get_user_by_zalo_id(zalo_id)


@_safe_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    zalo_id = str(user.id)

    existing = get_user_by_zalo_id(zalo_id)

    if not existing:
        active_companies = (
            supabase.table("companies")
            .select("company_id")
            .eq("is_active", True)
            .neq("company_id", "default")
            .execute()
        )
        auto_company_id = (
            active_companies.data[0]["company_id"]
            if len(active_companies.data) == 1
            else "default"
        )

        supabase.table("users").insert(
            {
                "zalo_id": zalo_id,
                "username": getattr(user, "display_name", ""),
                "full_name": getattr(user, "display_name", ""),
                "role": "member",
                "company_id": auto_company_id,
            }
        ).execute()

        welcome = (
            f"Xin chao {getattr(user, 'display_name', 'ban')}!\n\n"
            "Toi la Driftless — AI Agent cua cong ty ban.\n"
            "Hoi toi bat cu dieu gi ve quy trinh, tai lieu, hay du an.\n\n"
            "Go /help de xem cac lenh co san."
        )

        if auto_company_id == "default" and len(active_companies.data) > 1:
            welcome += "\n\nNeu chua thay tai lieu, hay dung /join [invite_code] de vao dung cong ty."

        await update.message.reply_text(welcome)
    else:
        await update.message.reply_text(
            f"Chao lai {getattr(user, 'display_name', 'ban')}! Toi co the giup gi cho ban?"
        )


@_safe_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Driftless — AI Agent cua cong ty ban\n\n"
        "Kien thuc:\n"
        "Hoi bat cu dieu gi ve quy trinh, tai lieu\n\n"
        "Analytics:\n"
        "Hoi ve KPI, tien do, hieu suat team\n\n"
        "Du bao:\n"
        "Hoi ve deadline risk, forecast\n\n"
        "Commands:\n"
        "/mytasks — Xem tasks cua ban\n"
        "/mytasks [ten] — Xem tasks cua nguoi khac\n"
        "/onboarding — Bat dau onboarding\n"
        "/next — Buoc tiep theo\n"
        "/summary — Bao cao tong quan (PM/Admin)\n"
        "/riskalert — Risk alert (PM/Admin)\n"
        "/feedback [noi dung] — Gui feedback an danh\n"
        "/viewfeedback — Xem feedback (Admin)\n"
        "/adddoc [link] — Them Google Sheets/Docs (Admin)\n"
        "/removedoc [link] — Xoa tai lieu (Admin)\n"
        "/listdocs — Danh sach tai lieu (PM/Admin)\n"
        "/resyncdocs — Sync lai tat ca (Admin)\n"
        "/syncstatus — Trang thai sync (PM/Admin)\n"
        "/myrole — Xem role cua ban\n"
        "/setrole — Set role (Admin)\n"
        "/join [code] — Tham gia cong ty"
    )


@_safe_handler
async def onboarding_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user:
        await update.message.reply_text("Go /start truoc nhe.")
        return

    zalo_id = str(update.effective_user.id)
    init_onboarding_zalo(zalo_id)
    content, _ = get_current_step_content_zalo(
        zalo_id, user.get("company_id", "pilot")
    )
    await update.message.reply_text(strip_markdown(content))


@_safe_handler
async def next_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user:
        return

    zalo_id = str(update.effective_user.id)
    content, _ = advance_onboarding_zalo(zalo_id)
    await update.message.reply_text(strip_markdown(content))


@_safe_handler
async def my_tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user:
        return

    if context.args:
        name = " ".join(context.args)
        result = get_tasks_by_name(name)
    else:
        result = get_my_tasks(user)

    await update.message.reply_text(strip_markdown(result))


@_safe_handler
async def add_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chi Admin moi them duoc tai lieu.")
        return

    if not context.args:
        await update.message.reply_text(
            "Cu phap: /adddoc [link Google Sheets hoac Docs]\n"
            "Nho share tai lieu cho service account truoc!"
        )
        return

    url = context.args[0]
    zalo_id = str(update.effective_user.id)
    company_id = user.get("company_id", "pilot")

    success, message = add_source(url, company_id, zalo_id)
    await update.message.reply_text(strip_markdown(message))


@_safe_handler
async def remove_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chi Admin moi xoa duoc tai lieu.")
        return

    if not context.args:
        await update.message.reply_text(
            "Cu phap: /removedoc [link Google Sheets hoac Docs]"
        )
        return

    url = context.args[0]
    company_id = user.get("company_id", "pilot")
    success, message = remove_source(url, company_id)
    await update.message.reply_text(strip_markdown(message))


@_safe_handler
async def list_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chi Admin va PM moi xem duoc.")
        return

    company_id = user.get("company_id", "pilot")
    result = list_sources(company_id)
    await update.message.reply_text(strip_markdown(result))


@_safe_handler
async def resync_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chi Admin moi sync duoc.")
        return

    company_id = user.get("company_id", "pilot")
    result = resync_all_sources(company_id)
    await update.message.reply_text(strip_markdown(result))


@_safe_handler
async def sync_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chi Admin va PM moi xem duoc.")
        return

    company_id = user.get("company_id", "default")
    result = (
        supabase.table("data_sources")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        await update.message.reply_text("Chua co tai lieu nao.")
        return

    lines = ["Trang thai sync:\n"]
    for src in result.data:
        last_synced = src.get("last_synced")
        if last_synced:
            synced_str = last_synced[:16].replace("T", " ")
            status = f"OK {synced_str}"
        else:
            status = "Chua sync"

        title = src.get("title") or src.get("source_id", "")
        lines.append(f"{title}\n   {status}\n")

    lines.append("Auto-sync moi gio 1 lan")
    await update.message.reply_text("\n".join(lines))


@_safe_handler
async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Cu phap: /feedback [noi dung feedback cua ban]\n"
            "Feedback hoan toan an danh."
        )
        return

    content = " ".join(context.args)
    user = _get_zalo_user(update)
    company_id = user.get("company_id", "pilot") if user else "pilot"

    success = submit_feedback(content, company_id)
    if success:
        await update.message.reply_text(
            "Feedback cua ban da duoc gui an danh.\nCam on ban da dong gop!"
        )
    else:
        await update.message.reply_text("Loi khi gui feedback. Vui long thu lai.")


@_safe_handler
async def view_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chi Admin moi xem duoc feedback.")
        return

    summary = get_feedback_summary(user.get("company_id", "pilot"))
    await update.message.reply_text(strip_markdown(summary))


@_safe_handler
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chi Admin va PM moi xem duoc summary.")
        return

    try:
        answer = get_quick_summary()
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo summary error: {e}")
        await update.message.reply_text("Loi khi tao summary.")


@_safe_handler
async def risk_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chi Admin va PM moi dung duoc.")
        return

    try:
        alert = get_risk_alert()
        if alert:
            await update.message.reply_text(strip_markdown(alert))
        else:
            await update.message.reply_text(
                "Khong co rui ro nghiem trong nao. Moi thu dang on!"
            )
    except Exception as e:
        logger.error(f"Zalo risk_alert error: {e}")
        await update.message.reply_text("Loi khi tao risk alert.")


@_safe_handler
async def my_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zalo_id = str(update.effective_user.id)

    result = (
        supabase.table("users")
        .select("role, full_name")
        .eq("zalo_id", zalo_id)
        .execute()
    )

    if result.data:
        user = result.data[0]
        role_label = {"admin": "Admin", "pm": "PM", "member": "Member"}.get(
            user["role"], user["role"]
        )
        await update.message.reply_text(f"Role cua ban: {role_label.upper()}")
    else:
        await update.message.reply_text("Ban chua dang ky. Go /start truoc nhe.")


@_safe_handler
async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zalo_id = str(update.effective_user.id)

    caller = (
        supabase.table("users")
        .select("role")
        .eq("zalo_id", zalo_id)
        .execute()
    )

    if not caller.data or caller.data[0]["role"] != "admin":
        await update.message.reply_text("Chi admin moi dung duoc lenh nay.")
        return

    args = context.args
    if not args or len(args) != 2:
        await update.message.reply_text(
            "Cu phap: /setrole [username] [role]\n"
            "Role hop le: admin, pm, member"
        )
        return

    username = args[0].lstrip("@")
    new_role = args[1].lower()

    if new_role not in {"admin", "pm", "member"}:
        await update.message.reply_text("Role khong hop le. Chon: admin, pm, member")
        return

    result = (
        supabase.table("users")
        .update({"role": new_role})
        .eq("username", username)
        .execute()
    )

    if result.data:
        await update.message.reply_text(f"Da set {username} thanh {new_role}")
    else:
        await update.message.reply_text(f"Khong tim thay {username}.")


@_safe_handler
async def join_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.company import join_company_by_code_zalo

    if not context.args:
        await update.message.reply_text("Cu phap: /join [invite code]")
        return

    zalo_id = str(update.effective_user.id)
    code = context.args[0]
    success, message = join_company_by_code_zalo(zalo_id, code)
    await update.message.reply_text(message)


@_safe_handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages — route through intent detection."""
    text = update.message.text
    zalo_id = str(update.effective_user.id)
    user = get_user_by_zalo_id(zalo_id)

    if not user:
        await update.message.reply_text("Ban chua dang ky. Go /start truoc nhe.")
        return

    intent = detect_intent(text)
    company_id = user.get("company_id", "pilot")

    if intent == Intent.KNOWLEDGE_QUERY:
        await _handle_knowledge(update, text, company_id)
    elif intent == Intent.ANALYTICS_QUERY:
        await _handle_analytics(update, text, company_id)
    elif intent == Intent.FORECAST_QUERY:
        await _handle_forecast(update, text)
    elif intent == Intent.SUPPORT_REQUEST:
        await _handle_support(update, text, user, company_id)
    else:
        await update.message.reply_text(
            "Toi chua hieu cau hoi. Ban co the hoi ro hon khong?"
        )


async def _handle_knowledge(update: Update, text: str, company_id: str):
    try:
        answer = answer_question(text, company_id)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo knowledge error: {e}")
        await update.message.reply_text("Xin loi, toi gap loi khi tim kiem. Vui long thu lai.")


async def _handle_analytics(update: Update, text: str, company_id: str):
    try:
        answer = analyze_query(text, company_id)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo analytics error: {e}")
        await update.message.reply_text("Xin loi, toi gap loi khi phan tich. Vui long thu lai.")


async def _handle_forecast(update: Update, text: str):
    try:
        answer = answer_forecast(text)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo forecast error: {e}")
        await update.message.reply_text("Loi khi du bao. Vui long thu lai.")


async def _handle_support(update: Update, text: str, user: dict, company_id: str):
    draft_keywords = ["viet", "draft", "soan", "tao", "giup toi viet"]

    if any(kw in text.lower() for kw in draft_keywords):
        try:
            result = draft_document(text, user)
            await update.message.reply_text(strip_markdown(result))
        except Exception as e:
            logger.error(f"Zalo draft error: {e}")
            await update.message.reply_text("Loi khi soan tai lieu.")
    else:
        await _handle_knowledge(update, text, company_id)


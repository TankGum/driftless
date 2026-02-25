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
    list_sources,
    parse_source,
    remove_source,
    resync_all_sources,
)
from platforms.zalo.formatter import strip_markdown
from support.drafter import draft_document
from support.feedback import get_feedback_summary, submit_feedback
from support.onboarding import (
    advance_onboarding_zalo,
    get_current_step_content_zalo,
    init_onboarding_zalo,
)
from support.task_helper import get_my_tasks, get_tasks_by_name


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
                    await update.message.reply_text("Xin lỗi, tôi gặp lỗi. Vui lòng thử lại.")
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
            active_companies.data[0]["company_id"] if len(active_companies.data) == 1 else "default"
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
            f"Xin chào {getattr(user, 'display_name', 'bạn')}!\n\n"
            "Tôi là Driftless — AI Agent của công ty bạn.\n"
            "Hỏi tôi bất cứ điều gì về quy trình, tài liệu, hay dự án.\n\n"
            "Gõ /help để xem các lệnh có sẵn."
        )

        if auto_company_id == "default" and len(active_companies.data) > 1:
            welcome += "\n\nNếu chưa thấy tài liệu, hãy dùng /join [invite_code] để vào đúng công ty."

        await update.message.reply_text(welcome)
    else:
        await update.message.reply_text(
            f"Chào lại {getattr(user, 'display_name', 'bạn')}! Tôi có thể giúp gì cho bạn?"
        )


@_safe_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Driftless — AI Agent của công ty bạn\n\n"
        "Kiến thức:\n"
        "Hỏi bất cứ điều gì về quy trình, tài liệu\n\n"
        "Analytics:\n"
        "Hỏi về KPI, tiến độ, hiệu suất team\n\n"
        "Dự báo:\n"
        "Hỏi về deadline risk, forecast\n\n"
        "Commands:\n"
        "/mytasks — Xem tasks của bạn\n"
        "/mytasks [tên] — Xem tasks của người khác\n"
        "/onboarding — Bắt đầu onboarding\n"
        "/next — Bước tiếp theo\n"
        "/summary — Báo cáo tổng quan (PM/Admin)\n"
        "/riskalert — Risk alert (PM/Admin)\n"
        "/feedback [nội dung] — Gửi feedback ẩn danh\n"
        "/viewfeedback — Xem feedback (Admin)\n"
        "/adddoc [link] — Thêm nguồn tài liệu (Admin)\n"
        "/removedoc [link] — Xóa tài liệu (Admin)\n"
        "/listdocs — Danh sách tài liệu (PM/Admin)\n"
        "/resyncdocs — Sync lại tất cả (Admin)\n"
        "/syncstatus — Trạng thái sync (PM/Admin)\n"
        "/myrole — Xem role của bạn\n"
        "/setrole — Set role (Admin)\n"
        "/join [code] — Tham gia công ty"
    )


@_safe_handler
async def onboarding_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user:
        await update.message.reply_text("Gõ /start trước nhé.")
        return

    zalo_id = str(update.effective_user.id)
    init_onboarding_zalo(zalo_id)
    content, _ = get_current_step_content_zalo(zalo_id, user.get("company_id", "pilot"))
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
        await update.message.reply_text("Chỉ Admin mới thêm được tài liệu.")
        return

    if not context.args:
        await update.message.reply_text(
            "Cú pháp: /adddoc [link nguồn dữ liệu]\n"
            "Nhớ share tài liệu cho service account trước!"
        )
        return

    url = context.args[0]
    zalo_id = str(update.effective_user.id)
    company_id = user.get("company_id", "pilot")

    _, message = add_source(url, company_id, zalo_id)
    await update.message.reply_text(strip_markdown(message))


@_safe_handler
async def remove_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chỉ Admin mới xóa được tài liệu.")
        return

    if not context.args:
        await update.message.reply_text("Cú pháp: /removedoc [link nguồn dữ liệu]")
        return

    url = context.args[0]
    company_id = user.get("company_id", "pilot")
    _, message = remove_source(url, company_id)
    await update.message.reply_text(strip_markdown(message))


@_safe_handler
async def list_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chỉ Admin và PM mới xem được.")
        return

    company_id = user.get("company_id", "pilot")
    result = list_sources(company_id)
    await update.message.reply_text(strip_markdown(result))


@_safe_handler
async def resync_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chỉ Admin mới sync được.")
        return

    company_id = user.get("company_id", "pilot")
    result = resync_all_sources(company_id)
    await update.message.reply_text(strip_markdown(result))


@_safe_handler
async def sync_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chỉ Admin và PM mới xem được.")
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
        await update.message.reply_text("Chưa có tài liệu nào.")
        return

    lines = ["Trạng thái sync:\n"]
    for src in result.data:
        last_synced = src.get("last_synced")
        if last_synced:
            synced_str = last_synced[:16].replace("T", " ")
            status = f"OK {synced_str}"
        else:
            status = "Chưa sync"

        title = src.get("title") or src.get("source_id", "")
        lines.append(f"{title}\n   {status}\n")

    lines.append("Auto-sync mỗi giờ 1 lần")
    await update.message.reply_text("\n".join(lines))


@_safe_handler
async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Cú pháp: /feedback [nội dung feedback của bạn]\n"
            "Feedback hoàn toàn ẩn danh."
        )
        return

    content = " ".join(context.args)
    user = _get_zalo_user(update)
    company_id = user.get("company_id", "pilot") if user else "pilot"

    success = submit_feedback(content, company_id)
    if success:
        await update.message.reply_text(
            "Feedback của bạn đã được gửi ẩn danh.\nCảm ơn bạn đã đóng góp!"
        )
    else:
        await update.message.reply_text("Lỗi khi gửi feedback. Vui lòng thử lại.")


@_safe_handler
async def view_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chỉ Admin mới xem được feedback.")
        return

    summary = get_feedback_summary(user.get("company_id", "pilot"))
    await update.message.reply_text(strip_markdown(summary))


@_safe_handler
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chỉ Admin và PM mới xem được summary.")
        return

    try:
        answer = get_quick_summary()
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo summary error: {e}")
        await update.message.reply_text("Lỗi khi tạo summary.")


@_safe_handler
async def risk_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("Chỉ Admin và PM mới dùng được.")
        return

    try:
        alert = get_risk_alert()
        if alert:
            await update.message.reply_text(strip_markdown(alert))
        else:
            await update.message.reply_text("Không có rủi ro nghiêm trọng nào. Mọi thứ đang ổn!")
    except Exception as e:
        logger.error(f"Zalo risk_alert error: {e}")
        await update.message.reply_text("Lỗi khi tạo risk alert.")


@_safe_handler
async def my_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zalo_id = str(update.effective_user.id)

    result = supabase.table("users").select("role, full_name").eq("zalo_id", zalo_id).execute()

    if result.data:
        user = result.data[0]
        role_label = {"admin": "Admin", "pm": "PM", "member": "Member"}.get(
            user["role"], user["role"]
        )
        await update.message.reply_text(f"Role của bạn: {role_label.upper()}")
    else:
        await update.message.reply_text("Bạn chưa đăng ký. Gõ /start trước nhé.")


@_safe_handler
async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zalo_id = str(update.effective_user.id)

    caller = supabase.table("users").select("role").eq("zalo_id", zalo_id).execute()

    if not caller.data or caller.data[0]["role"] != "admin":
        await update.message.reply_text("Chỉ admin mới dùng được lệnh này.")
        return

    args = context.args
    if not args or len(args) != 2:
        await update.message.reply_text(
            "Cú pháp: /setrole [username] [role]\nRole hợp lệ: admin, pm, member"
        )
        return

    username = args[0].lstrip("@")
    new_role = args[1].lower()

    if new_role not in {"admin", "pm", "member"}:
        await update.message.reply_text("Role không hợp lệ. Chọn: admin, pm, member")
        return

    result = supabase.table("users").update({"role": new_role}).eq("username", username).execute()

    if result.data:
        await update.message.reply_text(f"Đã set {username} thành {new_role}")
    else:
        await update.message.reply_text(f"Không tìm thấy {username}.")


@_safe_handler
async def join_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.company import join_company_by_code_zalo

    if not context.args:
        await update.message.reply_text("Cú pháp: /join [invite code]")
        return

    zalo_id = str(update.effective_user.id)
    code = context.args[0]
    _, message = join_company_by_code_zalo(zalo_id, code)
    await update.message.reply_text(message)


@_safe_handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages and route through intent detection."""
    text = update.message.text
    zalo_id = str(update.effective_user.id)
    user = get_user_by_zalo_id(zalo_id)

    if not user:
        await update.message.reply_text("Bạn chưa đăng ký. Gõ /start trước nhé.")
        return

    if user.get("role") == "admin":
        source_id, _ = parse_source(text)
        add_keywords = [
            "thêm",
            "add",
            "sync",
            "index",
            "đọc file",
            "doc",
            "sheet",
            "pdf",
        ]
        if source_id and any(k in text.lower() for k in add_keywords):
            company_id = user.get("company_id", "pilot")
            zalo_id = str(update.effective_user.id)
            _, message = add_source(text, company_id, zalo_id)
            await update.message.reply_text(strip_markdown(message))
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
        await update.message.reply_text("Tôi chưa hiểu câu hỏi. Bạn có thể hỏi rõ hơn không?")


async def _handle_knowledge(update: Update, text: str, company_id: str):
    try:
        answer = answer_question(text, company_id)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo knowledge error: {e}")
        await update.message.reply_text("Xin lỗi, tôi gặp lỗi khi tìm kiếm. Vui lòng thử lại.")


async def _handle_analytics(update: Update, text: str, company_id: str):
    try:
        answer = analyze_query(text, company_id)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo analytics error: {e}")
        await update.message.reply_text("Xin lỗi, tôi gặp lỗi khi phân tích. Vui lòng thử lại.")


async def _handle_forecast(update: Update, text: str):
    try:
        answer = answer_forecast(text)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo forecast error: {e}")
        await update.message.reply_text("Lỗi khi dự báo. Vui lòng thử lại.")


async def _handle_support(update: Update, text: str, user: dict, company_id: str):
    draft_keywords = ["viet", "viết", "draft", "soan", "soạn", "tao", "tạo", "giup toi viet", "giúp tôi viết"]

    if any(kw in text.lower() for kw in draft_keywords):
        try:
            result = draft_document(text, user)
            await update.message.reply_text(strip_markdown(result))
        except Exception as e:
            logger.error(f"Zalo draft error: {e}")
            await update.message.reply_text("Lỗi khi soạn tài liệu.")
    else:
        await _handle_knowledge(update, text, company_id)

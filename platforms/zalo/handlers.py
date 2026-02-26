from zalo_bot import Update
from zalo_bot.ext import ContextTypes

from analytics.analyzer import analyze_query
from core.auth import get_user_by_zalo_id
from core.logger import logger
from core.orchestrator import process as orchestrate
from database.supabase import supabase
from knowledge.retriever import answer_question
from knowledge.source_manager import (
    add_source,
    remove_source,
    list_sources,
    resync_all_sources,
)
from support.drafter import draft_document
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
                        "Xin lỗi, tôi gặp lỗi. Vui lòng thử lại."
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
        "Lệnh:\n"
        "/adddoc [link] — Thêm Google Sheets/Docs (Admin)\n"
        "/removedoc [link] — Xóa tài liệu (Admin)\n"
        "/listdocs — Danh sách tài liệu (PM/Admin)\n"
        "/resyncdocs — Sync lại tất cả (Admin)\n"
        "/syncstatus — Trạng thái sync (PM/Admin)\n"
        "/myrole — Xem role của bạn\n"
        "/setrole — Đặt role (Admin)\n"
        "/join [code] — Tham gia công ty"
    )


@_safe_handler
async def add_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = _get_zalo_user(update)
    if not user or user["role"] != "admin":
        await update.message.reply_text("Chỉ Admin mới thêm được tài liệu.")
        return

    if not context.args:
        await update.message.reply_text(
            "Cú pháp: /adddoc [link Google Sheets hoặc Docs]\n"
            "Nhớ share tài liệu cho service account trước!"
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
        await update.message.reply_text("Chỉ Admin mới xóa được tài liệu.")
        return

    if not context.args:
        await update.message.reply_text(
            "Cú pháp: /removedoc [link Google Sheets hoặc Docs]"
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
        await update.message.reply_text(f"Role của bạn: {role_label.upper()}")
    else:
        await update.message.reply_text("Bạn chưa đăng ký. Gõ /start trước nhé.")


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
        await update.message.reply_text("Chỉ admin mới dùng được lệnh này.")
        return

    args = context.args
    if not args or len(args) != 2:
        await update.message.reply_text(
            "Cú pháp: /setrole [username] [role]\n"
            "Role hợp lệ: admin, pm, member"
        )
        return

    username = args[0].lstrip("@")
    new_role = args[1].lower()

    if new_role not in {"admin", "pm", "member"}:
        await update.message.reply_text("Role không hợp lệ. Chọn: admin, pm, member")
        return

    result = (
        supabase.table("users")
        .update({"role": new_role})
        .eq("username", username)
        .execute()
    )

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
    success, message = join_company_by_code_zalo(zalo_id, code)
    await update.message.reply_text(message)


@_safe_handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages — route through intent detection."""
    text = update.message.text
    zalo_id = str(update.effective_user.id)
    user = get_user_by_zalo_id(zalo_id)

    if not user:
        await update.message.reply_text("Bạn chưa đăng ký. Gõ /start trước nhé.")
        return

    company_id = user.get("company_id", "pilot")
    try:
        answer = orchestrate(text, company_id, user)
        await update.message.reply_text(strip_markdown(answer))
    except Exception as e:
        logger.error(f"Zalo orchestrator error: {e}")
        await update.message.reply_text("Xin lỗi, tôi gặp lỗi. Vui lòng thử lại.")


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
    draft_keywords = ["viet", "draft", "soan", "tao", "giup toi viet"]

    if any(kw in text.lower() for kw in draft_keywords):
        try:
            result = draft_document(text, user)
            await update.message.reply_text(strip_markdown(result))
        except Exception as e:
            logger.error(f"Zalo draft error: {e}")
            await update.message.reply_text("Lỗi khi soạn tài liệu.")
    else:
        await _handle_knowledge(update, text, company_id)

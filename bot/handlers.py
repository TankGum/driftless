from telegram import Update
from telegram.ext import ContextTypes

from analytics.analyzer import analyze_query, get_quick_summary
from core.auth import get_user
from core.decorators import safe_handler, admin_only, pm_or_above
from core.logger import logger
from core.router import Intent, detect_intent
from database.supabase import supabase
from forecasting.responder import answer_forecast, get_risk_alert
from knowledge.retriever import answer_question
from knowledge.source_manager import add_source, remove_source, list_sources, resync_all_sources
from support.feedback import submit_feedback, get_feedback_summary
from support.onboarding import (
    advance_onboarding,
    get_current_step_content,
    init_onboarding,
)
from support.drafter import draft_document
from support.task_helper import get_my_tasks, get_tasks_by_name


@safe_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id

    logger.info(f"start command invoked by {telegram_id}")

    existing = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if not existing.data:
        supabase.table("users").insert(
            {
                "telegram_id": telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "role": "member",
            }
        ).execute()

        await update.message.reply_text(
            f" Xin chào {user.first_name}!\n\n"
            "Tôi là Driftless — AI Agent của công ty bạn.\n"
            "Hỏi tôi bất cứ điều gì về quy trình, tài liệu, hay dự án.\n\n"
            "Gõ /help để xem các lệnh có sẵn."
        )
    else:
        await update.message.reply_text(
            f"Chào lại {user.first_name}! Tôi có thể giúp gì cho bạn?"
        )


@safe_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " *Driftless — AI Agent của công ty bạn*\n\n"
        "* Kiến thức:*\n"
        "Hỏi bất cứ điều gì về quy trình, tài liệu\n\n"
        "* Analytics:*\n"
        "Hỏi về KPI, tiến độ, hiệu suất team\n\n"
        "* Dự báo:*\n"
        "Hỏi về deadline risk, forecast\n\n"
        "*⚙️ Commands:*\n"
        "/mytasks — Xem tasks của bạn (hoặc /mytasks @name)\n"
        "/onboarding — Bắt đầu onboarding\n"
        "/next — Bước tiếp theo trong onboarding\n"
        "/summary — Báo cáo tổng quan _(PM/Admin)_\n"
        "/riskalert — Risk alert _(PM/Admin)_\n"
        "/feedback `nội dung` — Gửi feedback ẩn danh\n"
        "/viewfeedback — Xem feedback _(Admin)_\n"
        "/adddoc `link` — Thêm Google Sheets/Docs mới _(Admin)_\n"
        "/removedoc `id` — Xóa tài liệu _(Admin)_\n"
        "/listdocs — Xem danh sách tài liệu _(PM/Admin)_\n"
        "/resyncdocs — Sync lại tất cả _(Admin)_\n"
        "/myrole — Xem role của bạn\n"
        "/setrole — Set role _(Admin)_",
        parse_mode="Markdown",
    )


@safe_handler
async def onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước nhé.")
        return

    init_onboarding(user["telegram_id"])
    content, _ = get_current_step_content(user["telegram_id"])
    await update.message.reply_text(content, parse_mode="Markdown")


@safe_handler
async def next_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        return

    content, _ = advance_onboarding(user["telegram_id"])
    await update.message.reply_text(content, parse_mode="Markdown")


@safe_handler
async def my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        return

    if context.args:
        name = " ".join(context.args)
        processing = await update.message.reply_text(f" Đang tìm tasks của {name}...")
        result = get_tasks_by_name(name)
    else:
        processing = await update.message.reply_text(" Đang tìm tasks của bạn...")
        result = get_my_tasks(user)

    await processing.delete()
    await update.message.reply_text(result, parse_mode="Markdown")


@safe_handler
@admin_only
async def add_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user or user["role"] != "admin":
        await update.message.reply_text("⛔ Chỉ Admin mới thêm được tài liệu.")
        return

    if not context.args:
        await update.message.reply_text(
            " *Cách thêm tài liệu:*\n\n"
            "`/adddoc [link Google Sheets hoặc Docs]`\n\n"
            "*Ví dụ:*\n"
            "`/adddoc https://docs.google.com/spreadsheets/d/1ABC.../edit`\n"
            "`/adddoc https://docs.google.com/document/d/1XYZ.../edit`\n\n"
            "⚠️ Nhớ share tài liệu cho service account trước!",
            parse_mode="Markdown",
        )
        return

    url = context.args[0]
    company_id = user.get("company_id", "pilot")

    processing = await update.message.reply_text("⏳ Đang đọc và index tài liệu...")
    success, message = add_source(url, company_id, user["telegram_id"])
    await processing.delete()
    await update.message.reply_text(message, parse_mode="Markdown")


@safe_handler
@admin_only
async def remove_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user or user["role"] != "admin":
        await update.message.reply_text("⛔ Chỉ Admin mới xóa được tài liệu.")
        return

    if not context.args:
        await update.message.reply_text(
            " Cách xóa tài liệu:\n\n"
            "/removedoc [link Google Sheets hoặc Docs]\n\n"
            "Ví dụ:\n"
            "/removedoc https://docs.google.com/spreadsheets/d/1ABC.../edit\n\n"
            "Dùng /listdocs để xem danh sách tài liệu hiện có.",
            parse_mode="Markdown",
        )
        return

    url = context.args[0]
    company_id = user.get("company_id", "pilot")

    success, message = remove_source(url, company_id)
    await update.message.reply_text(message, parse_mode="Markdown")


@safe_handler
@pm_or_above
async def list_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("⛔ Chỉ Admin và PM mới xem được.")
        return

    company_id = user.get("company_id", "pilot")
    result = list_sources(company_id)
    await update.message.reply_text(result, parse_mode="Markdown")


@safe_handler
@admin_only
async def resync_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user or user["role"] != "admin":
        await update.message.reply_text("⛔ Chỉ Admin mới sync được.")
        return

    processing = await update.message.reply_text("Đang sync lại tất cả tài liệu...")
    company_id = user.get("company_id", "pilot")
    result = resync_all_sources(company_id)
    await processing.delete()
    await update.message.reply_text(result)


@safe_handler
@pm_or_above
async def sync_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
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

    lines = [" *Trạng thái sync:*\n"]

    for src in result.data:
        last_synced = src.get("last_synced")
        if last_synced:
            synced_str = last_synced[:16].replace("T", " ")
            status = f"✅ {synced_str}"
        else:
            status = "⚠️ Chưa sync"

        lines.append(f"*{src['title'] or src['source_id']}*\n   {status}\n")

    lines.append("_Auto-sync mỗi giờ 1 lần_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@safe_handler
async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            " *Gửi feedback ẩn danh:*\n\n"
            "Cú pháp: `/feedback nội dung feedback của bạn`\n\n"
            "_Feedback hoàn toàn ẩn danh — không ai biết bạn là ai._",
            parse_mode="Markdown",
        )
        return

    content = " ".join(args)
    user = get_user(update.effective_user.id)
    company_id = user.get("company_id", "pilot") if user else "pilot"

    success = submit_feedback(content, company_id)
    if success:
        await update.message.reply_text(
            "✅ Feedback của bạn đã được gửi ẩn danh.\n"
            "Cảm ơn bạn đã đóng góp để cải thiện công ty!"
        )
    else:
        await update.message.reply_text("Lỗi khi gửi feedback. Vui lòng thử lại.")


@safe_handler
@admin_only
async def view_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user or user["role"] != "admin":
        await update.message.reply_text("⛔ Chỉ Admin mới xem được feedback.")
        return

    summary = get_feedback_summary(user.get("company_id", "pilot"))
    await update.message.reply_text(summary, parse_mode="Markdown")


@safe_handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_type = update.message.chat.type
    telegram_id = update.effective_user.id
    user = get_user(telegram_id)

    if not user:
        await update.message.reply_text("Bạn chưa đăng ký. Gõ /start trước nhé.")
        return

    if chat_type in ["group", "supergroup"]:
        bot_username = context.bot.username
        is_mentioned = f"@{bot_username}" in text
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user.id == context.bot.id
        )

        if not is_mentioned and not is_reply_to_bot:
            return

        text = text.replace(f"@{bot_username}", "").strip()

    intent = detect_intent(text)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    if intent == Intent.KNOWLEDGE_QUERY:
        await handle_knowledge(update, text, user)
    elif intent == Intent.ANALYTICS_QUERY:
        await handle_analytics(update, text, user)
    elif intent == Intent.FORECAST_QUERY:
        await handle_forecast(update, text, user)
    elif intent == Intent.SUPPORT_REQUEST:
        await handle_support(update, text, user)
    else:
        await update.message.reply_text(
            "Tôi chưa hiểu câu hỏi. Bạn có thể hỏi rõ hơn không?"
        )


async def handle_knowledge(update: Update, text: str, user: dict):
    company_id = user.get("company_id", "pilot")

    processing_msg = await update.message.reply_text(" Đang suy nghĩ...")

    try:
        answer = answer_question(text, company_id)

        await processing_msg.delete()

        await update.message.reply_text(
            f" {answer}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(
            "Xin lỗi, tôi gặp lỗi khi tìm kiếm. Vui lòng thử lại."
        )
        print(f"Error in handle_knowledge: {e}")


async def handle_support(update: Update, text: str, user: dict):
    draft_keywords = ["viết", "draft", "soạn", "tạo", "giúp tôi viết"]

    if any(kw in text.lower() for kw in draft_keywords):
        processing = await update.message.reply_text("✍️ Đang soạn thảo...")
        try:
            result = draft_document(text, user)
            await processing.delete()
            await update.message.reply_text(result, parse_mode="Markdown")
        except Exception as e:
            await processing.delete()
            await update.message.reply_text("Lỗi khi soạn tài liệu.")
            print(f"Draft error: {e}")
    else:
        await handle_knowledge(update, text, user)


@safe_handler
async def handle_analytics(update: Update, text: str, user: dict):
    company_id = user.get("company_id", "pilot")
    processing_msg = await update.message.reply_text(" Đang phân tích dữ liệu...")

    try:
        answer = analyze_query(text, company_id)
        await processing_msg.delete()
        await update.message.reply_text(
            answer,
            parse_mode="Markdown",
        )
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(
            "Xin lỗi, tôi gặp lỗi khi phân tích. Vui lòng thử lại."
        )
        print(f"Error in handle_analytics: {e}")


@safe_handler
async def handle_forecast(update: Update, text: str, user: dict):
    processing_msg = await update.message.reply_text(" Đang dự báo...")

    try:
        answer = answer_forecast(text)
        await processing_msg.delete()
        await update.message.reply_text(
            answer,
            parse_mode="Markdown",
        )
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text("Lỗi khi dự báo. Vui lòng thử lại.")
        print(f"Error in handle_forecast: {e}")


@safe_handler
@pm_or_above
async def risk_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("⛔ Chỉ Admin và PM mới dùng được.")
        return

    processing_msg = await update.message.reply_text(" Đang scan rủi ro...")

    try:
        alert = get_risk_alert()
        await processing_msg.delete()

        if alert:
            await update.message.reply_text(alert, parse_mode="Markdown")
        else:
            await update.message.reply_text("✅ Không có rủi ro nghiêm trọng nào. Mọi thứ đang ổn!")
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text("Lỗi khi tạo risk alert.")
        print(f"Error in risk_alert: {e}")


@safe_handler
@pm_or_above
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = get_user(telegram_id)

    if not user or user["role"] not in {"admin", "pm"}:
        await update.message.reply_text("⛔ Chỉ Admin và PM mới xem được summary.")
        return

    processing_msg = await update.message.reply_text(" Đang tổng hợp báo cáo...")

    try:
        answer = get_quick_summary()
        await processing_msg.delete()
        await update.message.reply_text(answer, parse_mode="Markdown")
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text("Lỗi khi tạo summary.")
        print(f"Error in summary: {e}")


async def my_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    result = (
        supabase.table("users")
        .select("role, full_name")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if result.data:
        user = result.data[0]
        role_emoji = {"admin": "🛡️", "pm": "🎯", "member": "👤"}.get(
            user["role"], ""
        )
        await update.message.reply_text(
            f"{role_emoji} Role của bạn: *{user['role'].upper()}*",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Bạn chưa được đăng ký. Gõ /start trước nhé.")


async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    caller = (
        supabase.table("users")
        .select("role")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if not caller.data or caller.data[0]["role"] != "admin":
        await update.message.reply_text("⛔ Chỉ admin mới dùng được lệnh này.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "Cú pháp: `/setrole @username role`\n"
            "Role hợp lệ: `admin`, `pm`, `member`",
            parse_mode="Markdown",
        )
        return

    username = args[0].lstrip("@")
    new_role = args[1].lower()

    if new_role not in {"admin", "pm", "member"}:
        await update.message.reply_text(
            "Role không hợp lệ. Chọn: `admin`, `pm`, `member`",
            parse_mode="Markdown",
        )
        return

    result = (
        supabase.table("users")
        .update({"role": new_role})
        .eq("username", username)
        .execute()
    )

    if result.data:
        await update.message.reply_text(
            f"✅ Đã set @{username} thành `{new_role}`",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Không tìm thấy @{username}. Họ cần /start trước.",
            parse_mode="Markdown",
        )

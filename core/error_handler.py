from telegram import Update
from telegram.ext import ContextTypes
from core.logger import logger
import traceback

ERROR_MESSAGES = {
    "HttpError 403": "Tôi không có quyền đọc tài liệu này. Admin vui lòng kiểm tra lại quyền truy cập.",
    "HttpError 404": "Không tìm thấy tài liệu. Có thể đã bị xóa hoặc link sai.",
    "ConnectTimeout": "Kết nối bị timeout. Vui lòng thử lại sau.",
    "TimedOut": "Kết nối Telegram bị chậm. Vui lòng thử lại.",
    "Anthropic": "AI đang bận, vui lòng thử lại sau 30 giây.",
    "supabase": "Lỗi kết nối database. Vui lòng thử lại.",
    "InvalidURL": "Link không hợp lệ. Vui lòng kiểm tra lại.",
}


def get_friendly_message(error: Exception) -> str:
    error_str = str(error)
    for key, message in ERROR_MESSAGES.items():
        if key.lower() in error_str.lower():
            return message
    return "Có lỗi xảy ra. Vui lòng thử lại hoặc liên hệ admin."


async def global_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(
        f"Unhandled exception | "
        f"User: {update.effective_user.id if update and update.effective_user else 'unknown'} | "
        f"Error: {error} | "
        f"Traceback: {traceback.format_exc()}"
    )
    if update and update.message:
        friendly = get_friendly_message(error)
        await update.message.reply_text(f"⚠️ {friendly}")

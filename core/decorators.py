import functools

from core.logger import logger
from core.error_handler import get_friendly_message


def safe_handler(func):
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(
                f"Error in {func.__name__} | "
                f"User: {update.effective_user.id if update and update.effective_user else 'unknown'} | "
                f"Error: {e}"
            )
            friendly = get_friendly_message(e)
            if update and update.message:
                await update.message.reply_text(f"⚠️ {friendly}")
    return wrapper


def admin_only(func):
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        from core.auth import get_user
        user = get_user(update.effective_user.id)
        if not user or user["role"] != "admin":
            await update.message.reply_text("⛔ Chỉ Admin mới dùng được lệnh này.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def pm_or_above(func):
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        from core.auth import get_user
        user = get_user(update.effective_user.id)
        if not user or user["role"] not in {"admin", "pm"}:
            await update.message.reply_text("⛔ Chỉ Admin và PM mới dùng được lệnh này.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

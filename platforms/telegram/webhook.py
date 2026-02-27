"""Telegram webhook router for FastAPI.

Replaces polling mode: Telegram POSTs updates to /webhook/telegram.
Requires BASE_URL set in .env (public HTTPS URL).
"""
import os
from fastapi import APIRouter, Request, Response
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from config import TELEGRAM_TOKEN
from core.logger import logger

router = APIRouter(tags=["telegram"])

_application: Application | None = None


def _build_application() -> Application:
    """Build Telegram Application and register all handlers (one-time)."""
    from platforms.telegram.handlers import (
        start,
        help_command,
        handle_message,
        my_role,
        set_role,
        add_doc,
        remove_doc,
        list_docs,
        resync_docs,
        sync_status,
    )
    from core.error_handler import global_error_handler

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myrole", my_role))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CommandHandler("adddoc", add_doc))
    app.add_handler(CommandHandler("removedoc", remove_doc))
    app.add_handler(CommandHandler("listdocs", list_docs))
    app.add_handler(CommandHandler("resyncdocs", resync_docs))
    app.add_handler(CommandHandler("syncstatus", sync_status))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND
            & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
            handle_message,
        )
    )
    app.add_error_handler(global_error_handler)

    return app


def _get_application() -> Application:
    global _application
    if _application is None:
        _application = _build_application()
    return _application


async def setup_webhook(base_url: str) -> None:
    """Register webhook URL with Telegram. Call once on server startup."""
    webhook_url = f"{base_url.rstrip('/')}/webhook/telegram"
    app = _get_application()
    await app.initialize()
    await app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
    )
    logger.info(f"Telegram webhook set: {webhook_url}")


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram update and dispatch to handlers."""
    data = await request.json()
    app = _get_application()

    # Initialize application if not already done
    if not app.running:
        await app.initialize()
        await app.start()

    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return Response(content='{"ok": true}', media_type="application/json")

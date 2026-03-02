"""Zalo OA webhook router for FastAPI.

Replaces polling mode: Zalo POSTs events to /webhook/zalo.
"""
from fastapi import APIRouter, Request, Response
from core.logger import logger

router = APIRouter(tags=["zalo"])

_application = None


def _build_application():
    """Build Zalo Application and register all handlers (one-time)."""
    from zalo_bot.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from platforms.zalo.handlers import (
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
        join_company,
    )
    from config import ZALO_BOT_TOKEN

    app = ApplicationBuilder().token(ZALO_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myrole", my_role))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CommandHandler("adddoc", add_doc))
    app.add_handler(CommandHandler("removedoc", remove_doc))
    app.add_handler(CommandHandler("listdocs", list_docs))
    app.add_handler(CommandHandler("resyncdocs", resync_docs))
    app.add_handler(CommandHandler("syncstatus", sync_status))
    app.add_handler(CommandHandler("join", join_company))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return app


def _get_application():
    global _application
    if _application is None:
        try:
            _application = _build_application()
        except Exception as e:
            logger.error(f"Failed to build Zalo application: {e}")
    return _application


@router.post("/webhook/zalo")
async def zalo_webhook(request: Request):
    """Receive Zalo OA event and dispatch to handlers."""
    try:
        data = await request.json()
        app = _get_application()
        if app is None:
            return Response(
                content='{"ok": false, "error": "Zalo app not initialized"}',
                media_type="application/json",
                status_code=500,
            )
        # Delegate to zalo_bot framework's update processing
        if hasattr(app, "process_update"):
            await app.process_update(data)
        elif hasattr(app, "handle_update"):
            await app.handle_update(data)
        else:
            logger.warning("Zalo app has no process_update/handle_update method")
    except Exception as e:
        logger.error(f"Zalo webhook error: {e}", exc_info=True)

    return Response(content='{"ok": true}', media_type="application/json")

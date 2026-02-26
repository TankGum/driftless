import threading

from telegram.ext import (
    ApplicationBuilder as TelegramAppBuilder,
    CommandHandler as TelegramCommandHandler,
    MessageHandler as TelegramMessageHandler,
    filters as tg_filters,
)
from telegram.request import HTTPXRequest

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
from config import TELEGRAM_TOKEN, ZALO_BOT_TOKEN
from core.error_handler import global_error_handler
from core.logger import logger
from jobs.auto_sync import run_auto_sync


def build_telegram_app():
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        TelegramAppBuilder()
        .token(TELEGRAM_TOKEN)
        .request(request)
        .build()
    )

    app.add_handler(TelegramCommandHandler("start", start))
    app.add_handler(TelegramCommandHandler("help", help_command))
    app.add_handler(
        TelegramMessageHandler(
            tg_filters.TEXT
            & ~tg_filters.COMMAND
            & (tg_filters.ChatType.PRIVATE | tg_filters.ChatType.GROUPS),
            handle_message,
        )
    )
    app.add_handler(TelegramCommandHandler("myrole", my_role))
    app.add_handler(TelegramCommandHandler("setrole", set_role))
    app.add_handler(TelegramCommandHandler("adddoc", add_doc))
    app.add_handler(TelegramCommandHandler("removedoc", remove_doc))
    app.add_handler(TelegramCommandHandler("listdocs", list_docs))
    app.add_handler(TelegramCommandHandler("resyncdocs", resync_docs))
    app.add_handler(TelegramCommandHandler("syncstatus", sync_status))

    app.add_error_handler(global_error_handler)

    app.job_queue.run_repeating(
        callback=run_auto_sync,
        interval=3600,
        first=60,
        name="auto_sync",
    )
    logger.info("Auto-sync scheduled every 1 hour")

    return app


def build_zalo_app():
    from zalo_bot.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

    from platforms.zalo.handlers import (
        start as zalo_start,
        help_command as zalo_help,
        handle_message as zalo_handle_message,
        my_role as zalo_my_role,
        set_role as zalo_set_role,
        add_doc as zalo_add_doc,
        remove_doc as zalo_remove_doc,
        list_docs as zalo_list_docs,
        resync_docs as zalo_resync_docs,
        sync_status as zalo_sync_status,
        join_company as zalo_join,
    )

    app = ApplicationBuilder().token(ZALO_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", zalo_start))
    app.add_handler(CommandHandler("help", zalo_help))
    app.add_handler(CommandHandler("myrole", zalo_my_role))
    app.add_handler(CommandHandler("setrole", zalo_set_role))
    app.add_handler(CommandHandler("adddoc", zalo_add_doc))
    app.add_handler(CommandHandler("removedoc", zalo_remove_doc))
    app.add_handler(CommandHandler("listdocs", zalo_list_docs))
    app.add_handler(CommandHandler("resyncdocs", zalo_resync_docs))
    app.add_handler(CommandHandler("syncstatus", zalo_sync_status))
    app.add_handler(CommandHandler("join", zalo_join))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            zalo_handle_message,
        )
    )

    return app


def _run_zalo():
    """Run Zalo bot in its own thread with its own event loop."""
    try:
        zalo_app = build_zalo_app()
        logger.info("Zalo bot started (polling)")
        zalo_app.run_polling()
    except Exception as e:
        logger.error(f"Zalo bot crashed: {e}", exc_info=True)


def main():
    if ZALO_BOT_TOKEN:
        zalo_thread = threading.Thread(target=_run_zalo, daemon=True)
        zalo_thread.start()

    telegram_app = build_telegram_app()
    logger.info("Driftless bot is running...")
    telegram_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()



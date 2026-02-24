from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)
from bot.handlers import (
    start,
    help_command,
    handle_message,
    my_role,
    set_role,
    summary,
    risk_alert,
    onboarding,
    next_step,
    my_tasks,
    feedback,
    view_feedback,
    add_doc,
    remove_doc,
    list_docs,
    resync_docs,
    sync_status,
)
from config import TELEGRAM_TOKEN
from core.error_handler import global_error_handler
from core.logger import logger
from jobs.auto_sync import run_auto_sync
from telegram.request import HTTPXRequest


def main():
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .request(request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & (
                filters.ChatType.PRIVATE | filters.ChatType.GROUPS
            ),
            handle_message,
        )
    )
    app.add_handler(CommandHandler("myrole", my_role))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("riskalert", risk_alert))
    app.add_handler(CommandHandler("onboarding", onboarding))
    app.add_handler(CommandHandler("next", next_step))
    app.add_handler(CommandHandler("mytasks", my_tasks))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(CommandHandler("viewfeedback", view_feedback))
    app.add_handler(CommandHandler("adddoc", add_doc))
    app.add_handler(CommandHandler("removedoc", remove_doc))
    app.add_handler(CommandHandler("listdocs", list_docs))
    app.add_handler(CommandHandler("resyncdocs", resync_docs))
    app.add_handler(CommandHandler("syncstatus", sync_status))

    app.add_error_handler(global_error_handler)

    app.job_queue.run_repeating(
        callback=run_auto_sync,
        interval=3600,
        first=60,
        name="auto_sync",
    )
    logger.info(" Auto-sync scheduled every 1 hour")
    logger.info(" Driftless bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

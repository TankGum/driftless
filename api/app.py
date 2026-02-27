"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, upload, admin
from core.logger import logger


def _start_scheduler():
    """Start APScheduler for hourly auto-sync (replaces Telegram job_queue)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from jobs.auto_sync import run_auto_sync_apscheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_auto_sync_apscheduler,
        trigger="interval",
        hours=1,
        id="auto_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler: auto-sync scheduled every 1 hour")
    return scheduler


def _start_telegram_polling():
    import threading
    from platforms.telegram.webhook import _build_application

    def _run():
        tg_app = _build_application()
        logger.info("Telegram bot started (polling)")
        tg_app.run_polling(drop_pending_updates=True)

    threading.Thread(target=_run, daemon=True, name="telegram-polling").start()


def _start_zalo_polling():
    import threading

    def _run():
        try:
            from zalo_bot.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
            from platforms.zalo.handlers import (
                start, help_command, handle_message, my_role, set_role,
                add_doc, remove_doc, list_docs, resync_docs, sync_status, join_company,
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
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            logger.info("Zalo bot started (polling)")
            app.run_polling()
        except Exception as e:
            logger.error(f"Zalo polling error: {e}")

    threading.Thread(target=_run, daemon=True, name="zalo-polling").start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""
    logger.info("Driftless API starting up...")
    scheduler = _start_scheduler()
    yield
    logger.info("Driftless API shutting down...")
    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Driftless API",
        description="AI Agent nội bộ — FastAPI + LangChain + Chainlit",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS (allow Chainlit frontend)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded

        limiter = Limiter(key_func=get_remote_address, default_limits=["30/hour"])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    except ImportError:
        logger.warning("slowapi not installed — rate limiting disabled")

    # Domain API routers
    app.include_router(chat.router)
    app.include_router(upload.router)
    app.include_router(admin.router)

    # Platform: polling mode + keep webhook routes (not registered with Telegram/Zalo, harmless)
    from config import TELEGRAM_TOKEN, ZALO_BOT_TOKEN
    if TELEGRAM_TOKEN:
        from platforms.telegram.webhook import router as tg_router
        app.include_router(tg_router)
        _start_telegram_polling()
    if ZALO_BOT_TOKEN:
        from platforms.zalo.webhook import router as zalo_router
        app.include_router(zalo_router)
        _start_zalo_polling()

    # Mount Chainlit at root
    try:
        from chainlit.utils import mount_chainlit
        mount_chainlit(app=app, target="chainlit_app.py", path="/")
        logger.info("Chainlit mounted at /")
    except ImportError:
        logger.warning("chainlit not installed — WebUI unavailable")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "driftless"}

    return app

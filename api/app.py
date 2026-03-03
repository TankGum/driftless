"""FastAPI application factory."""
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.routers import chat, upload, admin, provision
from config import TENANT_ID, COMPANY_NAME
from core.logger import logger


def _start_scheduler():
    """Start APScheduler for hourly auto-sync (replaces Telegram job_queue)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from jobs.auto_sync import run_auto_sync_apscheduler, run_chat_cleanup_apscheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_auto_sync_apscheduler,
        trigger="interval",
        hours=1,
        id="auto_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        run_chat_cleanup_apscheduler,
        trigger="cron",
        hour=3, minute=0,
        id="chat_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler: auto-sync scheduled every 1 hour")
    logger.info("APScheduler: chat session cleanup scheduled daily at 03:00")
    return scheduler


def _start_telegram_polling():
    import threading
    from platforms.telegram.webhook import _build_application

    def _run():
        tg_app = _build_application()
        logger.info("Telegram bot started (polling)")
        tg_app.run_polling(drop_pending_updates=True, stop_signals=None)

    threading.Thread(target=_run, daemon=True, name="telegram-polling").start()


def _start_zalo_polling():
    import threading

    def _run():
        import asyncio

        async def _polling_loop_with_backoff():
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

            # Override default 5s timeouts — Zalo API can be slow
            from zalo_bot.request import HTTPXRequest
            _req = HTTPXRequest(connect_timeout=30.0, read_timeout=35.0, write_timeout=30.0, pool_timeout=30.0)
            app.bot._request = (_req, _req)

            await app.bot.initialize()
            logger.info("Zalo bot started (polling)")
            backoff = 5  # seconds between retries on error
            try:
                while True:
                    try:
                        update = await app.bot.get_update(timeout=30)
                        backoff = 5  # reset on success
                    except Exception as exc:
                        logger.warning(f"Zalo getUpdates error (retry in {backoff}s): {exc}")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 120)
                        continue
                    if update:
                        try:
                            await app.process_update(update)
                        except Exception as exc:
                            logger.error(f"Zalo process_update error: {exc}")
                    else:
                        await asyncio.sleep(1)
            finally:
                await app.bot.shutdown()

        import time
        backoff = 10
        while True:
            try:
                asyncio.run(_polling_loop_with_backoff())
            except Exception as e:
                logger.warning(f"Zalo polling crashed (retry in {backoff}s): {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)

    threading.Thread(target=_run, daemon=True, name="zalo-polling").start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""
    logger.info("Driftless API starting up...")
    if TENANT_ID > 0:
        from core.company import ensure_company_initialized
        import asyncio
        await asyncio.to_thread(
            ensure_company_initialized, str(TENANT_ID), COMPANY_NAME
        )
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

    @app.middleware("http")
    async def portal_auth_token_cookie_bridge(request: Request, call_next):
        """Bridge portal auth_token query param to cookie before Chainlit auth runs."""
        token = request.query_params.get("auth_token")
        if token:
            remaining = [
                (k, v) for (k, v) in request.query_params.multi_items() if k != "auth_token"
            ]
            target_url = request.url.path
            if remaining:
                target_url = f"{target_url}?{urlencode(remaining, doseq=True)}"

            response = RedirectResponse(url=target_url, status_code=307)
            response.set_cookie(
                key="auth_token",
                value=token,
                max_age=86400,  # 24h, matching existing handoff behavior
                path="/",
                samesite="lax",
                httponly=True,
            )
            return response

        response = await call_next(request)

        # Chainlit logs out its own session on POST /logout, but we also need to
        # clear portal handoff cookie to prevent immediate auto re-login.
        if request.method.upper() == "POST" and request.url.path == "/logout":
            response.delete_cookie(key="auth_token", path="/")

        return response

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
    app.include_router(provision.router)

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

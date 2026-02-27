"""Auto-sync job — syncs all active company data sources hourly.

Two modes:
1. APScheduler (new) — used when running via FastAPI/uvicorn (main.py)
2. Telegram job_queue (legacy) — kept for backwards compatibility

APScheduler is started in api/app.py via _start_scheduler().
"""
from knowledge.source_manager import resync_all_sources
from database.supabase import supabase
from core.logger import logger


def _sync_all() -> None:
    """Core sync logic — platform-agnostic."""
    logger.info("Auto-sync started...")

    result = (
        supabase.table("companies")
        .select("company_id, name")
        .eq("is_active", True)
        .execute()
    )

    companies = result.data or []
    for company in companies:
        company_id = company["company_id"]
        try:
            message = resync_all_sources(company_id)
            logger.info(f"Synced {company_id}: {message}")
        except Exception as e:
            logger.error(f"Sync failed for {company_id}: {e}")

    logger.info("Auto-sync completed!")


async def run_auto_sync_apscheduler() -> None:
    """APScheduler async job — called by AsyncIOScheduler in api/app.py."""
    _sync_all()


async def run_auto_sync(context) -> None:
    """Legacy Telegram job_queue callback — kept for compatibility."""
    _sync_all()

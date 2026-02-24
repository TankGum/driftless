from knowledge.source_manager import resync_all_sources
from database.supabase import supabase
from core.logger import logger


async def run_auto_sync(context):
    """Chạy sync tất cả tenants mỗi giờ"""
    logger.info(" Auto-sync started...")

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
            logger.info(f"✅ Synced {company_id}: {message}")
        except Exception as e:
            logger.error(f"❌ Sync failed for {company_id}: {e}")

    logger.info("✅ Auto-sync completed!")

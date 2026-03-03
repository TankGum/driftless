"""Portal usage sync helpers."""

from __future__ import annotations

import httpx

from config import PORTAL_API_KEY, PORTAL_URL, TENANT_ID
from core.logger import logger
from database.supabase import supabase


def count_active_sources(company_id: str) -> int:
    """Count active knowledge sources for a company."""
    try:
        result = (
            supabase.table("data_sources")
            .select("id")
            .eq("company_id", company_id)
            .eq("is_active", True)
            .execute()
        )
        return len(result.data or [])
    except Exception as exc:
        logger.warning(f"Failed to count active sources for {company_id}: {exc}")
        return 0


def sync_portal_usage(
    company_id: str,
    *,
    questions_used: int | None = None,
    sources_count: int | None = None,
    users_count: int | None = None,
) -> None:
    """Best-effort usage sync from agent to portal tenant record."""
    if not PORTAL_URL or not TENANT_ID or not PORTAL_API_KEY:
        return

    payload: dict[str, int] = {}
    if questions_used is not None:
        payload["questions_used"] = questions_used
    if sources_count is not None:
        payload["sources_count"] = sources_count
    if users_count is not None:
        payload["users_count"] = users_count

    if not payload:
        return

    try:
        httpx.post(
            f"{PORTAL_URL}/api/v1/tenants/{TENANT_ID}/usage",
            json=payload,
            headers={"X-Api-Key": PORTAL_API_KEY},
            timeout=5.0,
        )
    except Exception as exc:
        # Non-blocking: business flow must not fail if portal is unavailable.
        logger.warning(f"Portal usage sync failed for {company_id}: {exc}")

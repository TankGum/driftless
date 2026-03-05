"""Source quota checks for knowledge-base additions."""

from __future__ import annotations

import httpx

from config import PORTAL_API_KEY, PORTAL_URL, TENANT_ID
from core.logger import logger
from core.portal_usage import count_active_sources
from database.supabase import supabase


def quota_exceeded_message(count: int, limit: int) -> str:
    return (
        f"⛔ Đã đạt giới hạn nguồn dữ liệu ({count}/{limit}) đã được sử dụng hết.\n"
        "Nâng cấp subscription để mở rộng dung lượng và tiếp tục sử dụng đầy đủ tính năng."
    )


def _fetch_sources_limit() -> int | None:
    """Fetch tenant sources_limit from portal API (best-effort)."""
    if not PORTAL_URL or not TENANT_ID or not PORTAL_API_KEY:
        return None

    try:
        resp = httpx.get(
            f"{PORTAL_URL}/api/v1/tenants/{TENANT_ID}/limits",
            headers={"X-Api-Key": PORTAL_API_KEY},
            timeout=5.0,
        )
    except Exception as exc:
        logger.warning(f"Could not fetch tenant limits from portal: {exc}")
        return None

    if resp.status_code != 200:
        logger.warning(f"Portal limits returned {resp.status_code}: {resp.text[:200]}")
        return None

    try:
        data = resp.json()
        value = data.get("sources_limit")
        return int(value) if value is not None else None
    except Exception as exc:
        logger.warning(f"Invalid limits payload from portal: {exc}")
        return None


def _is_source_active(company_id: str, source_id: str) -> bool:
    result = (
        supabase.table("data_sources")
        .select("id")
        .eq("company_id", company_id)
        .eq("source_id", source_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def can_add_source(
    company_id: str,
    source_id: str,
    *,
    allow_replace: bool = False,
) -> tuple[bool, str]:
    """Return whether adding a source is allowed under current quota."""
    if allow_replace:
        return True, ""

    # Updating an already-active source does not increase source count.
    if _is_source_active(company_id, source_id):
        return True, ""

    active_count = count_active_sources(company_id)
    limit = _fetch_sources_limit()
    if limit is None:
        # Fail-open when portal is unavailable/unconfigured.
        return True, ""

    if active_count >= limit:
        logger.info(
            "Source limit exceeded: company_id=%s source_id=%s active=%s limit=%s",
            company_id,
            source_id,
            active_count,
            limit,
        )
        return False, quota_exceeded_message(active_count, limit)

    return True, ""

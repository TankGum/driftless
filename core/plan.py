"""Plan/trial enforcement logic — platform-agnostic.

Plans:
- trial: tối đa 7 ngày VÀ 50 queries
- pro:   plan='pro' AND pro_expires_at > now()
- expired: tất cả trường hợp còn lại
"""
from datetime import datetime, timezone

TRIAL_MAX_DAYS = 7
TRIAL_MAX_QUERIES = 50


def get_plan_status(company: dict) -> str:
    """Return 'trial', 'pro', or 'expired' for a company dict."""
    plan = company.get("plan", "trial")

    if plan == "pro":
        pro_expires_at = company.get("pro_expires_at")
        if pro_expires_at:
            # Parse ISO string if needed
            if isinstance(pro_expires_at, str):
                pro_expires_at = datetime.fromisoformat(pro_expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if pro_expires_at > now:
                return "pro"
        return "expired"

    # trial plan
    trial_started_at = company.get("trial_started_at")
    trial_query_count = company.get("trial_query_count", 0) or 0

    if trial_started_at:
        if isinstance(trial_started_at, str):
            trial_started_at = datetime.fromisoformat(trial_started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_elapsed = (now - trial_started_at).days
        if days_elapsed >= TRIAL_MAX_DAYS:
            return "expired"

    if trial_query_count >= TRIAL_MAX_QUERIES:
        return "expired"

    return "trial"


def check_query_allowed(company_id: str) -> tuple[bool, str]:
    """Fetch company from DB and check if query is allowed.

    Returns (True, "") if allowed, or (False, "thông báo") if blocked.
    """
    from database.supabase import supabase

    result = (
        supabase.table("companies")
        .select("plan, trial_started_at, trial_query_count, pro_expires_at")
        .eq("company_id", company_id)
        .single()
        .execute()
    )

    if not result.data:
        # Company không tồn tại — cho phép (không block)
        return True, ""

    company = result.data
    status = get_plan_status(company)

    if status in ("trial", "pro"):
        return True, ""

    # expired
    trial_query_count = company.get("trial_query_count", 0) or 0
    if trial_query_count >= TRIAL_MAX_QUERIES:
        msg = (
            "⏰ *Tài khoản dùng thử đã hết lượt hỏi* (tối đa 50 câu hỏi).\n\n"
            "Để tiếp tục sử dụng, vui lòng liên hệ đội ngũ Driftless để nâng cấp lên *Pro*."
        )
    else:
        msg = (
            "⏰ *Thời gian dùng thử đã kết thúc* (tối đa 7 ngày).\n\n"
            "Để tiếp tục sử dụng, vui lòng liên hệ đội ngũ Driftless để nâng cấp lên *Pro*."
        )

    return False, msg


def increment_query_count(company_id: str) -> None:
    """Increment trial_query_count by 1 (only for trial plan companies)."""
    from database.supabase import supabase

    result = (
        supabase.table("companies")
        .select("trial_query_count, plan")
        .eq("company_id", company_id)
        .single()
        .execute()
    )

    if not result.data or result.data.get("plan") != "trial":
        return

    current = result.data.get("trial_query_count") or 0
    supabase.table("companies").update(
        {"trial_query_count": current + 1}
    ).eq("company_id", company_id).execute()

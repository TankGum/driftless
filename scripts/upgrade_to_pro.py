"""Upgrade a company from trial to Pro plan.

Usage:
    python scripts/upgrade_to_pro.py --company-id cong-ty-a --months 12
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def upgrade(company_id: str, months: int) -> None:
    from database.supabase import supabase

    # Verify company exists
    result = (
        supabase.table("companies")
        .select("company_id, name, plan")
        .eq("company_id", company_id)
        .single()
        .execute()
    )

    if not result.data:
        print(f"[ERROR] Company '{company_id}' not found.")
        sys.exit(1)

    company = result.data
    expires = datetime.now(timezone.utc) + timedelta(days=30 * months)

    supabase.table("companies").update({
        "plan": "pro",
        "pro_expires_at": expires.isoformat(),
    }).eq("company_id", company_id).execute()

    print(f"✅ {company['name']} ({company_id}) upgraded to Pro until {expires.strftime('%Y-%m-%d')}.")


def main():
    parser = argparse.ArgumentParser(description="Upgrade a company to Pro plan")
    parser.add_argument("--company-id", required=True, help="company_id in Supabase")
    parser.add_argument("--months", type=int, default=12, help="Duration in months (default: 12)")

    args = parser.parse_args()

    if args.months <= 0:
        print("[ERROR] --months must be a positive integer.")
        sys.exit(1)

    upgrade(args.company_id, args.months)


if __name__ == "__main__":
    main()

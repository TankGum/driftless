from typing import Optional

from database.supabase import supabase


def get_user(telegram_id: int) -> Optional[dict]:
    result = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )
    return result.data[0] if result.data else None


def is_admin(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    return bool(user and user["role"] == "admin")


def is_pm_or_above(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    return bool(user and user["role"] in {"admin", "pm"})


def get_user_by_zalo_id(zalo_id: str) -> Optional[dict]:
    result = (
        supabase.table("users")
        .select("*")
        .eq("zalo_id", zalo_id)
        .execute()
    )
    return result.data[0] if result.data else None


def is_admin_zalo(zalo_id: str) -> bool:
    user = get_user_by_zalo_id(zalo_id)
    return bool(user and user["role"] == "admin")


def is_pm_or_above_zalo(zalo_id: str) -> bool:
    user = get_user_by_zalo_id(zalo_id)
    return bool(user and user["role"] in {"admin", "pm"})

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


_PROFILE_FIELDS = {"department", "position", "email", "phone", "bio", "full_name"}


def update_user_profile(telegram_id: int = None, zalo_id: str = None, **fields) -> bool:
    """Update user profile fields (department, position, email, phone, bio, full_name)."""
    updates = {k: v for k, v in fields.items() if k in _PROFILE_FIELDS and v is not None}
    if not updates:
        return False

    if telegram_id:
        result = supabase.table("users").update(updates).eq("telegram_id", telegram_id).execute()
    elif zalo_id:
        result = supabase.table("users").update(updates).eq("zalo_id", zalo_id).execute()
    else:
        return False

    return bool(result.data)


def get_user_profile_text(user: dict) -> str:
    """Format user profile as display text."""
    role_emoji = {"admin": "🛡️", "pm": "🎯", "member": "👤"}.get(user.get("role", ""), "")
    lines = [
        f"{role_emoji} *{user.get('full_name', 'N/A')}* ({user.get('role', 'member').upper()})",
    ]

    if user.get("department"):
        lines.append(f"Phòng ban: {user['department']}")
    if user.get("position"):
        lines.append(f"Chức vụ: {user['position']}")
    if user.get("email"):
        lines.append(f"Email: {user['email']}")
    if user.get("phone"):
        lines.append(f"SĐT: {user['phone']}")
    if user.get("bio"):
        lines.append(f"Bio: {user['bio']}")

    if len(lines) == 1:
        lines.append("_Chưa có thông tin cá nhân. Dùng /editprofile để cập nhật._")

    return "\n".join(lines)

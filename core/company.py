from database.supabase import supabase
from core.logger import logger
import random
import string


def generate_company_id(name: str) -> str:
    base = name.lower().replace(" ", "_").replace("-", "_")
    base = ''.join(c for c in base if c.isalnum() or c == "_")
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{base[:20]}_{suffix}"


def create_company(name: str, admin_telegram_id: int, drive_folder_id: str = None) -> dict:
    company_id = generate_company_id(name)

    insert_data = {
        "company_id": company_id,
        "name": name,
        "admin_telegram_id": admin_telegram_id,
        "is_active": True,
    }
    if drive_folder_id:
        insert_data["drive_folder_id"] = drive_folder_id

    result = supabase.table("companies").insert(insert_data).execute()

    supabase.table("users").upsert(
        {
            "telegram_id": admin_telegram_id,
            "company_id": company_id,
            "role": "admin",
        },
        on_conflict="telegram_id",
    ).execute()

    logger.info(f"Created company: {name} ({company_id})")
    return result.data[0] if result.data else None


def get_company(company_id: str) -> dict:
    result = supabase.table("companies").select("*").eq("company_id", company_id).eq("is_active", True).execute()
    return result.data[0] if result.data else None


def get_user_company(telegram_id: int) -> str:
    from core.auth import get_user

    user = get_user(telegram_id)
    if not user:
        return "default"
    return user.get("company_id") or "default"


def get_invite_link(company_id: str) -> str:
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    supabase.table("companies").update({"invite_code": code}).eq("company_id", company_id).execute()
    return code


def join_company_by_code(telegram_id: int, code: str) -> tuple[bool, str]:
    result = (
        supabase.table("companies")
        .select("*")
        .eq("invite_code", code.upper())
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        return False, "❌ Invite code không hợp lệ hoặc đã hết hạn."

    company = result.data[0]

    supabase.table("users").update(
        {
            "company_id": company["company_id"],
            "role": "member",
        }
    ).eq("telegram_id", telegram_id).execute()

    return True, f"✅ Đã tham gia *{company['name']}*! Gõ /help để bắt đầu."


def set_drive_folder(company_id: str, drive_folder_id: str) -> bool:
    """Update Drive folder ID for a company."""
    result = (
        supabase.table("companies")
        .update({"drive_folder_id": drive_folder_id})
        .eq("company_id", company_id)
        .execute()
    )
    return bool(result.data)


def get_user_company_by_zalo(zalo_id: str) -> str:
    from core.auth import get_user_by_zalo_id

    user = get_user_by_zalo_id(zalo_id)
    if not user:
        return "default"
    return user.get("company_id") or "default"


def join_company_by_code_zalo(zalo_id: str, code: str) -> tuple[bool, str]:
    result = (
        supabase.table("companies")
        .select("*")
        .eq("invite_code", code.upper())
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        return False, "Invite code khong hop le hoac da het han."

    company = result.data[0]

    supabase.table("users").update(
        {
            "company_id": company["company_id"],
            "role": "member",
        }
    ).eq("zalo_id", zalo_id).execute()

    return True, f"Da tham gia {company['name']}! Gui 'help' de bat dau."

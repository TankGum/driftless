"""scripts/manage_users.py — Quản lý tài khoản Driftless (tất cả platforms)."""
import sys
import getpass
import bcrypt

sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from database.supabase import supabase
from config import DEFAULT_COMPANY_ID

_company_id = DEFAULT_COMPANY_ID or "pilot"
VALID_ROLES = {"admin", "pm", "member"}


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def _prompt_password(label: str = "Mật khẩu") -> str:
    while True:
        pw = getpass.getpass(f"  {label}: ")
        if len(pw) >= 6:
            return pw
        print("  Mật khẩu phải có ít nhất 6 ký tự.")


def _find_user(username: str):
    r = (
        supabase.table("users")
        .select("*")
        .eq("username", username)
        .eq("company_id", _company_id)
        .execute()
    )
    return r.data[0] if r.data else None


def list_users():
    r = (
        supabase.table("users")
        .select("id, username, full_name, role, telegram_id, zalo_id, password_hash")
        .eq("company_id", _company_id)
        .order("id")
        .execute()
    )
    if not r.data:
        print("  Chưa có tài khoản nào.")
        return

    print(f"\n  Company: {_company_id}")
    print(f"  {'ID':<5} {'Username':<18} {'Họ tên':<22} {'Role':<8} {'Platform':<14} {'WebUI'}")
    print("  " + "-" * 76)
    for u in r.data:
        parts = []
        if u.get("telegram_id"):
            parts.append("Telegram")
        if u.get("zalo_id"):
            parts.append("Zalo")
        platform = " ".join(parts) if parts else "WebUI only"
        has_pw = "Có" if u.get("password_hash") else "-"
        print(
            f"  {u['id']:<5} {(u.get('username') or ''):<18} "
            f"{(u.get('full_name') or ''):<22} {(u.get('role') or ''):<8} "
            f"{platform:<14} {has_pw}"
        )


def create_user():
    print("\n-- Tạo tài khoản WebUI mới --")
    username = input("  Username: ").strip()
    if not username:
        return
    if _find_user(username):
        print(f"  Lỗi: '{username}' đã tồn tại.")
        return

    full_name = input("  Họ và tên: ").strip() or username
    role = input("  Vai trò (admin/pm/member) [member]: ").strip().lower()
    if role not in VALID_ROLES:
        role = "member"
    password = _prompt_password()

    try:
        supabase.table("users").insert({
            "username": username,
            "full_name": full_name,
            "role": role,
            "company_id": _company_id,
            "password_hash": _hash(password),
        }).execute()
        print(f"  Tạo '{username}' ({role}) thành công.")
    except Exception as e:
        print(f"  Lỗi: {e}")


def grant_webui_access():
    print("\n-- Cấp quyền đăng nhập WebUI (cho Telegram/Zalo user) --")
    username = input("  Username (tên Telegram/Zalo của họ): ").strip()
    user = _find_user(username)
    if not user:
        print(f"  Không tìm thấy '{username}'. Họ cần /start trước.")
        return

    pw = _prompt_password("Mật khẩu WebUI mới")
    supabase.table("users").update({"password_hash": _hash(pw)}).eq("id", user["id"]).execute()
    print(f"  Đã cấp mật khẩu WebUI cho '{username}'.")


def set_role():
    print("\n-- Thay đổi vai trò --")
    username = input("  Username: ").strip()
    user = _find_user(username)
    if not user:
        print(f"  Không tìm thấy '{username}'.")
        return

    print(f"  Vai trò hiện tại: {user.get('role')}")
    new_role = input("  Vai trò mới (admin/pm/member): ").strip().lower()
    if new_role not in VALID_ROLES:
        print("  Vai trò không hợp lệ.")
        return

    supabase.table("users").update({"role": new_role}).eq("id", user["id"]).execute()
    print(f"  Đổi '{username}' → '{new_role}' thành công. Có hiệu lực ngay.")


def delete_user():
    print("\n-- Xóa tài khoản --")
    username = input("  Username: ").strip()
    user = _find_user(username)
    if not user:
        print(f"  Không tìm thấy '{username}'.")
        return

    confirm = input(
        f"  Xác nhận xóa '{username}' ({user.get('role')})? (yes/no): "
    ).strip().lower()
    if confirm != "yes":
        print("  Hủy.")
        return

    supabase.table("users").delete().eq("id", user["id"]).execute()
    print(f"  Đã xóa '{username}'.")


MENU = [
    ("Xem danh sách tài khoản", list_users),
    ("Tạo tài khoản WebUI mới", create_user),
    ("Cấp mật khẩu WebUI cho Telegram/Zalo user", grant_webui_access),
    ("Thay đổi vai trò", set_role),
    ("Xóa tài khoản", delete_user),
    ("Thoát", None),
]


def main():
    print(f"\n{'=' * 50}")
    print("  DRIFTLESS — Quản lý tài khoản")
    print(f"  Company: {_company_id}")
    print("=" * 50)

    while True:
        print()
        for i, (label, _) in enumerate(MENU, 1):
            print(f"  [{i}] {label}")

        choice = input("\nChọn: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(MENU)):
            print("  Lựa chọn không hợp lệ.")
            continue

        label, fn = MENU[int(choice) - 1]
        if fn is None:
            print("  Tạm biệt!")
            break
        fn()


if __name__ == "__main__":
    main()

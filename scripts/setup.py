import os
import sys

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()

from config import (
    CLAUDE_API_KEY,
    GOOGLE_CREDENTIALS_PATH,
    SUPABASE_KEY,
    SUPABASE_URL,
    TELEGRAM_TOKEN,
    ZALO_BOT_TOKEN,
)
from core.logger import logger
from database.supabase import supabase


def check_env():
    """Kiểm tra tất cả env vars bắt buộc"""
    required = [
        "TELEGRAM_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "CLAUDE_API_KEY",
        "GOOGLE_CREDENTIALS_PATH",
        "ZALO_BOT_TOKEN",
    ]

    missing = [k for k in required if not os.getenv(k)]

    if missing:
        print(f"❌ Thiếu các env vars: {', '.join(missing)}")
        print("Vui lòng điền đầy đủ vào file .env")
        return False

    print("✅ Env vars OK")
    return True


def check_google_credentials():
    """Kiểm tra Google credentials file"""
    path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    if not os.path.exists(path):
        print(f"❌ Không tìm thấy file: {path}")
        return False
    print("✅ Google credentials OK")
    return True


def check_supabase():
    """Kiểm tra kết nối Supabase"""
    try:
        supabase.table("users").select("id").limit(1).execute()
        print("✅ Supabase connection OK")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("Kiểm tra SUPABASE_URL và SUPABASE_KEY")
        return False


def check_tables():
    """Kiểm tra các bảng đã được tạo chưa"""
    tables = ["users", "companies", "data_sources", "documents", "document_chunks"]
    missing = []

    for table in tables:
        try:
            supabase.table(table).select("id").limit(1).execute()
        except Exception:
            missing.append(table)

    if missing:
        print(f"❌ Các bảng chưa được tạo: {', '.join(missing)}")
        print("Chạy file scripts/migrate.sql trong Supabase SQL Editor")
        return False

    print("✅ Database tables OK")
    return True


def create_admin(telegram_id: int, username: str, company_name: str):
    """Tạo admin account và company"""
    from core.company import create_company

    try:
        supabase.table("users").upsert(
            {
                "telegram_id": telegram_id,
                "username": username,
                "full_name": username,
                "role": "admin",
                "company_id": "default",
            },
            on_conflict="telegram_id",
        ).execute()

        company = create_company(company_name, telegram_id)

        if company:
            print(f"✅ Tạo company '{company_name}' thành công")
            print(f"   Company ID: {company['company_id']}")
            return True

        print("❌ Lỗi tạo company. Vui lòng thử lại.")
        return False

    except Exception as e:
        error = str(e)
        if "duplicate key" in error:
            print("⚠️  Telegram ID này đã tồn tại — đang update thông tin...")
            company = create_company(company_name, telegram_id)
            if company:
                print(f"✅ Cập nhật thành công! Company: '{company_name}'")
                return True
        elif "company_id" in error:
            print("❌ Thiếu cột company_id trong bảng users.")
            print("   Chạy SQL: alter table users add column if not exists company_id text default 'default';")
        else:
            print(f"❌ Lỗi không xác định: {error}")
        return False


def run_setup():
    print("\n" + "=" * 50)
    print("  DRIFTLESS — Setup Script")
    print("=" * 50 + "\n")

    checks = [
        check_env,
        check_google_credentials,
        check_supabase,
        check_tables,
    ]

    for check in checks:
        if not check():
            print("\n❌ Setup failed. Fix lỗi trên và chạy lại.")
            sys.exit(1)

    print("\n✅ Tất cả checks passed!\n")

    print("Nhập thông tin admin:")
    telegram_id = int(input("  Telegram ID của admin: "))
    username = input("  Username Telegram (không có @): ")
    company_name = input("  Tên công ty: ")

    if create_admin(telegram_id, username, company_name):
        print("\n" + "=" * 50)
        print("  ✅ Setup hoàn thành!")
        print("=" * 50)
        print("\nBước tiếp theo:")
        print("1. Chạy: python main.py")
        print("2. Mở Telegram, tìm bot và gõ /start")
        print("3. Dùng /adddoc để thêm tài liệu")
        print("4. Dùng /invite để tạo invite code cho team\n")
    else:
        print("\n❌ Setup failed.")
        sys.exit(1)


if __name__ == "__main__":
    run_setup()

import sys

sys.path.append(".")

from dotenv import load_dotenv

from database.supabase import supabase
from knowledge.indexer import sync_source

load_dotenv()

# Lấy sources từ database
result = (
    supabase.table("data_sources")
    .select("*")
    .eq("is_active", True)
    .execute()
)

if not result.data:
    print("Chưa có tài liệu nào. Dùng /adddoc trong Telegram để thêm.")
else:
    for src in result.data:
        source_id = (
            f"doc:{src['source_id']}"
            if src["source_type"] == "google_docs"
            else src["source_id"]
        )
        try:
            total = sync_source(source_id, src["company_id"])
            print(f"✅ {src['title'] or src['source_id']}: {total} chunks")
        except Exception as e:
            print(f"❌ Lỗi khi sync {src['source_id']}: {e}")

print("\n✅ All sources synced!")

"""Xóa document_chunks mồ côi (document đã bị xóa nhưng chunks còn sót).

Chạy thủ công hoặc định kỳ nếu nghi ngờ có orphan chunks sau can thiệp DB trực tiếp.

Usage:
    python scripts/cleanup_chunks.py [--dry-run]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client


def cleanup_orphan_chunks(dry_run: bool = False) -> None:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Find orphan chunk IDs: chunks whose document_id has no matching document row
    orphan_resp = (
        supabase
        .rpc("find_orphan_chunk_ids")
        .execute()
    )

    # Fallback: fetch all chunk document_ids and all document ids, diff in Python
    # (avoids needing a custom RPC function in Supabase)
    chunks_resp = supabase.table("document_chunks").select("id, document_id").execute()
    docs_resp = supabase.table("documents").select("id").execute()

    doc_ids = {row["id"] for row in docs_resp.data}
    orphan_ids = [
        row["id"]
        for row in chunks_resp.data
        if row["document_id"] not in doc_ids
    ]

    if not orphan_ids:
        print("Không tìm thấy orphan chunks.")
        return

    print(f"Tìm thấy {len(orphan_ids)} orphan chunks.")

    if dry_run:
        print("[dry-run] Không xóa. Chạy lại không có --dry-run để xóa thật.")
        return

    # Delete in batches of 500 to avoid request size limits
    batch_size = 500
    deleted = 0
    for i in range(0, len(orphan_ids), batch_size):
        batch = orphan_ids[i : i + batch_size]
        supabase.table("document_chunks").delete().in_("id", batch).execute()
        deleted += len(batch)
        print(f"  Đã xóa {deleted}/{len(orphan_ids)} chunks...")

    print(f"Hoàn tất: đã xóa {deleted} orphan chunks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dọn dẹp orphan document_chunks")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ hiển thị số lượng, không xóa thật",
    )
    args = parser.parse_args()
    cleanup_orphan_chunks(dry_run=args.dry_run)

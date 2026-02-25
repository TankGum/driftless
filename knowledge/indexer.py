import anthropic

from database.supabase import supabase
from knowledge.sheets_reader import (
    get_sheet_title,
    read_sheet,
    sheet_to_text,
    read_doc,
    doc_to_text,
    read_pdf,
    pdf_to_text,
)


claude = anthropic.Anthropic()


def get_embedding(text: str) -> list[float]:
    """Dùng Claude để tạo embedding"""
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": f"Summarize in 10 words: {text[:500]}",
            }
        ],
    )
    return None


def detect_source_type(source_id: str) -> str:
    """Detect loại source dựa trên ID hoặc URL"""
    if source_id.startswith("pdf:"):
        return "google_pdf"
    if source_id.startswith("doc:"):
        return "google_docs"
    return "google_sheets"


def sync_source(source_id: str, company_id: str = "pilot"):
    """Sync bất kỳ source nào — Sheets hoặc Docs"""
    source_type = detect_source_type(source_id)
    real_id = source_id.replace("pdf:", "").replace("doc:", "").replace("sheet:", "").strip()

    print(f"Syncing {source_type}: {real_id}")

    if source_type == "google_pdf":
        rows = read_pdf(real_id)
        chunks = pdf_to_text(rows)
        raw_title = rows[0]["_sheet_name"] if rows else real_id
        title = f"[PDF] {raw_title}"
    elif source_type == "google_docs":
        rows = read_doc(real_id)
        chunks = doc_to_text(rows)
        raw_title = rows[0]["_sheet_name"] if rows else real_id
        title = f"[Doc] {raw_title}"
    else:
        rows = read_sheet(real_id)
        chunks = sheet_to_text(rows)
        raw_title = get_sheet_title(real_id)
        title = f"[Sheet] {raw_title}"

    print(f"Found {len(chunks)} chunks")

    if not chunks:
        print(f"⚠️ No content found in {real_id}")
        return 0

    doc_result = supabase.table("documents").upsert(
        {
            "company_id": company_id,
            "source_type": source_type,
            "source_id": real_id,
            "title": title,
        }
    ).execute()

    doc_id = doc_result.data[0]["id"]

    supabase.table("document_chunks").delete().eq("document_id", doc_id).execute()

    for i, chunk in enumerate(chunks):
        supabase.table("document_chunks").insert(
            {
                "document_id": doc_id,
                "content": chunk,
                "row_number": i,
                "metadata": {"source_id": real_id, "source_type": source_type},
            }
        ).execute()

    print(f"✅ Synced {len(chunks)} chunks from {source_type}: {title}")
    return len(chunks)


def sync_sheet(sheet_id: str, company_id: str = "pilot"):
    """Backward compatible — vẫn dùng được như cũ"""
    return sync_source(sheet_id, company_id)

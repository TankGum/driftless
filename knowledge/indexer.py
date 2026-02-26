from database.supabase import supabase
from knowledge.embedder import embed_documents_batch
from knowledge.sheets_reader import (
    get_sheet_title,
    read_sheet,
    sheet_to_text,
    read_doc,
    doc_to_text,
    read_pdf,
    pdf_to_text,
)


def detect_source_type(source_id: str) -> str:
    """Detect loại source dựa trên ID hoặc URL"""
    if source_id.startswith("pdf:"):
        return "google_pdf"
    if source_id.startswith("doc:"):
        return "google_docs"
    return "google_sheets"


def sync_source(source_id: str, company_id: str = "pilot"):
    """Sync bất kỳ source nào — Sheets hoặc Docs.

    Chỉ gọi Voyage AI khi nội dung thực sự thay đổi so với lần sync trước.
    """
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

    # So sánh với chunks đang có trong DB
    existing = (
        supabase.table("document_chunks")
        .select("content, embedding")
        .eq("document_id", doc_id)
        .order("row_number")
        .execute()
    )
    existing_contents = [r["content"] for r in existing.data]
    existing_has_embeddings = existing.data and all(r.get("embedding") for r in existing.data)

    if existing_contents == chunks and existing_has_embeddings:
        print(f"⏭️  Không thay đổi, bỏ qua embedding: {title}")
        return len(chunks)

    # Nội dung mới hoặc chưa có embedding → embed lại
    supabase.table("document_chunks").delete().eq("document_id", doc_id).execute()

    print(f"Embedding {len(chunks)} chunks...")
    embeddings = embed_documents_batch(chunks)

    records = [
        {
            "document_id": doc_id,
            "content": chunk,
            "row_number": i,
            "metadata": {"source_id": real_id, "source_type": source_type, "title": title},
            "embedding": embedding,
        }
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    supabase.table("document_chunks").insert(records).execute()

    print(f"✅ Synced {len(chunks)} chunks from {source_type}: {title}")
    return len(chunks)


def sync_sheet(sheet_id: str, company_id: str = "pilot"):
    """Backward compatible — vẫn dùng được như cũ"""
    return sync_source(sheet_id, company_id)

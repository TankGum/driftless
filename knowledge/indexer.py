import os
import io
import time
import hashlib

from database.supabase import supabase
from core.portal_usage import count_active_sources, sync_portal_usage
from core.source_limits import can_add_source


def _insert_chunks_batched(records: list, batch_size: int = 5) -> None:
    """Insert document_chunks one batch at a time with retry + backoff.

    Keeps each request small (avoid SSL EOF) and retries transient
    connection timeouts before giving up.
    """
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        for attempt in range(3):
            try:
                supabase.table("document_chunks").insert(batch).execute()
                break
            except Exception as exc:
                if attempt == 2:
                    raise
                wait = 2 ** attempt  # 1s, 2s
                print(f"  Batch {i//batch_size} failed ({exc}), retrying in {wait}s...")
                time.sleep(wait)
        # Brief pause between batches — avoids hammering the connection pool
        if i + batch_size < len(records):
            time.sleep(0.3)
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
    _insert_chunks_batched(records)

    print(f"✅ Synced {len(chunks)} chunks from {source_type}: {title}")
    return len(chunks)


def sync_sheet(sheet_id: str, company_id: str = "pilot"):
    """Backward compatible — vẫn dùng được như cũ"""
    return sync_source(sheet_id, company_id)


def _read_local_pdf(path: str) -> list[str]:
    """Đọc PDF local: text layer trước, Tesseract OCR làm fallback."""
    import pypdf

    with open(path, "rb") as f:
        reader = pypdf.PdfReader(f)
        chunks = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                chunks.append(text)

    if chunks:
        return chunks

    # Fallback: OCR bằng Tesseract (PDF ảnh)
    try:
        import fitz
        import pytesseract
        from PIL import Image
        from config import TESSERACT_CMD

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        doc = fitz.open(path)
        ocr_chunks = []
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                try:
                    text = pytesseract.image_to_string(img, lang="vie+eng").strip()
                except pytesseract.TesseractError:
                    # Fallback nếu máy chưa có gói ngôn ngữ tiếng Việt.
                    text = pytesseract.image_to_string(img, lang="eng").strip()
                if text:
                    ocr_chunks.append(text)
        finally:
            doc.close()
        return ocr_chunks
    except Exception as e:
        print(f"  [OCR] Lỗi Tesseract: {e}")
        return []


def _read_local_docx(path: str) -> list[str]:
    """Đọc DOCX local, chunk theo paragraph (bỏ qua dòng trống)."""
    try:
        import docx
    except ImportError:
        raise ImportError("Cần cài python-docx: pip install python-docx")

    doc = docx.Document(path)
    chunks = []
    current = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            if current:
                chunks.append("\n".join(current))
                current = []
        else:
            current.append(text)
            # Chunk tối đa 1500 ký tự
            if sum(len(t) for t in current) > 1500:
                chunks.append("\n".join(current))
                current = []

    if current:
        chunks.append("\n".join(current))

    return [c for c in chunks if c.strip()]


def _read_local_txt(path: str) -> list[str]:
    """Đọc TXT local, chunk theo 1500 ký tự."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()

    chunk_size = 1500
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size) if text[i:i + chunk_size].strip()]


def _read_local_xlsx(path: str) -> list[str]:
    """Đọc XLSX local, chunk theo từng dòng dữ liệu trong từng sheet."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Cần cài openpyxl: pip install openpyxl")

    # File upload tạm có thể không có extension; đọc qua BytesIO để openpyxl không reject.
    with open(path, "rb") as f:
        xlsx_bytes = f.read()
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    max_chunk_len = 1500

    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if not cells:
                    continue
                line = f"[Sheet: {ws.title}] " + " | ".join(cells)
                if current_len + len(line) > max_chunk_len and current:
                    chunks.append("\n".join(current))
                    current = []
                    current_len = 0
                current.append(line)
                current_len += len(line) + 1
    finally:
        wb.close()

    if current:
        chunks.append("\n".join(current))

    return chunks


def sync_local_file(
    file_path: str,
    company_id: str,
    added_by: str,
    filename: str = "",
    force_replace: bool = False,
) -> tuple[bool, str, dict | None]:
    """Index một file local (PDF, DOCX, TXT) vào knowledge base.

    Args:
        file_path:     Đường dẫn tới file (có thể là temp path không có extension).
        filename:      Tên file gốc (dùng để detect extension và đặt title).
                       Nếu bỏ trống, lấy từ file_path.
        force_replace: Nếu True, xóa record cũ cùng content_hash trước khi index.

    Returns:
        (True,  "✅ ...", None)                          — thành công
        (False, "❌ ...", None)                          — lỗi thông thường
        (False, "DUPLICATE", {"source_id", "title"})    — trùng nội dung với file khác tên
    """
    filename = filename or os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    # Đọc text từ file
    try:
        if ext == ".pdf":
            text_chunks = _read_local_pdf(file_path)
        elif ext == ".docx":
            text_chunks = _read_local_docx(file_path)
        elif ext == ".txt":
            text_chunks = _read_local_txt(file_path)
        elif ext == ".xlsx":
            text_chunks = _read_local_xlsx(file_path)
        else:
            return False, f"❌ Định dạng '{ext}' chưa được hỗ trợ. Chấp nhận: .pdf, .docx, .txt, .xlsx", None
    except Exception as e:
        return False, f"❌ Không đọc được file: {e}", None

    if not text_chunks:
        return False, "⚠️ File không có nội dung text. Kiểm tra lại file.", None

    # Tính content hash để dedup theo nội dung
    content_hash = hashlib.sha256("\n".join(text_chunks).encode()).hexdigest()
    source_id = f"local:{filename}"
    title = f"[Upload] {filename}"
    source_type = "local_file"

    if not force_replace:
        # Kiểm tra trùng nội dung với file KHÁC tên
        dup = (
            supabase.table("data_sources")
            .select("source_id, title")
            .eq("company_id", company_id)
            .eq("content_hash", content_hash)
            .neq("source_id", source_id)
            .execute()
        )
        if dup.data:
            return False, "DUPLICATE", {
                "source_id": dup.data[0]["source_id"],
                "title": dup.data[0]["title"],
            }
    else:
        # Xóa record cũ cùng content_hash nhưng khác source_id
        old = (
            supabase.table("data_sources")
            .select("source_id")
            .eq("company_id", company_id)
            .eq("content_hash", content_hash)
            .neq("source_id", source_id)
            .execute()
        )
        if old.data:
            old_source_id = old.data[0]["source_id"]
            old_doc = (
                supabase.table("documents")
                .select("id")
                .eq("company_id", company_id)
                .eq("source_id", old_source_id)
                .execute()
            )
            if old_doc.data:
                supabase.table("document_chunks").delete().eq("document_id", old_doc.data[0]["id"]).execute()
                supabase.table("documents").delete().eq("id", old_doc.data[0]["id"]).execute()
            supabase.table("data_sources").delete().eq("company_id", company_id).eq("source_id", old_source_id).execute()

    # Tìm document record cũ nếu đã tồn tại (cùng source_id)
    allowed, limit_message = can_add_source(
        company_id,
        source_id,
        allow_replace=force_replace,
    )
    if not allowed:
        return False, limit_message, None

    existing_doc = (
        supabase.table("documents")
        .select("id")
        .eq("company_id", company_id)
        .eq("source_id", source_id)
        .execute()
    )
    if existing_doc.data:
        doc_id = existing_doc.data[0]["id"]
        supabase.table("documents").update({"title": title, "last_synced": "now()"}).eq("id", doc_id).execute()
    else:
        doc_result = supabase.table("documents").insert(
            {
                "company_id": company_id,
                "source_type": source_type,
                "source_id": source_id,
                "title": title,
            }
        ).execute()
        doc_id = doc_result.data[0]["id"]

    # Xóa chunks cũ rồi embed lại
    supabase.table("document_chunks").delete().eq("document_id", doc_id).execute()

    print(f"Embedding {len(text_chunks)} chunks từ {filename}...")
    embeddings = embed_documents_batch(text_chunks)

    records = [
        {
            "document_id": doc_id,
            "content": chunk,
            "row_number": i,
            "metadata": {"source_id": source_id, "source_type": source_type, "title": title},
            "embedding": embedding,
        }
        for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings))
    ]
    _insert_chunks_batched(records)

    # Ghi vào data_sources để hiện trong /listdocs
    supabase.table("data_sources").upsert(
        {
            "company_id": company_id,
            "source_type": source_type,
            "source_id": source_id,
            "title": title,
            "added_by": str(added_by),
            "is_active": True,
            "content_hash": content_hash,
        },
        on_conflict="company_id,source_id",
    ).execute()

    # Best-effort sync usage counters to portal.
    sync_portal_usage(company_id, sources_count=count_active_sources(company_id))

    return True, f"✅ Đã index **{filename}** ({len(text_chunks)} chunks)", None

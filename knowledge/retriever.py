import time

from anthropic import Anthropic

from config import CLAUDE_API_KEY
from database.supabase import supabase
from knowledge.sheets_reader import (
    doc_to_text,
    pdf_to_text,
    read_doc,
    read_pdf,
    read_sheet,
    search_drive_files,
    sheet_to_text,
)

claude = Anthropic(api_key=CLAUDE_API_KEY)

# File-level cache: {file_id: (timestamp, chunks)}
_file_cache: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL = 600  # 10 minutes


def _is_analytics_query(query: str) -> bool:
    """Detect if the query asks for analytics-style analysis."""
    text = (query or "").lower()
    keywords = [
        "phân tích", "phan tich",
        "so sánh", "so sanh",
        "thống kê", "thong ke",
        "kpi",
        "tiến độ", "tien do",
        "trend",
        "tổng hợp", "tong hop",
        "báo cáo", "bao cao",
        "hiệu suất", "hieu suat",
        "target",
        "achievement",
    ]
    return any(k in text for k in keywords)


def _read_file_chunks(file_meta: dict, max_chunks: int = 6) -> list[str]:
    """Read file content as chunks, with 10-minute cache."""
    file_id = file_meta.get("id")
    now = time.time()

    # Check cache
    if file_id in _file_cache:
        cached_time, cached_chunks = _file_cache[file_id]
        if now - cached_time < _CACHE_TTL:
            return cached_chunks[:max_chunks]

    mime_type = file_meta.get("mimeType", "")

    if mime_type == "application/vnd.google-apps.document":
        chunks = doc_to_text(read_doc(file_id))
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        chunks = sheet_to_text(read_sheet(file_id))
    elif mime_type == "application/pdf":
        title, pages = read_pdf(file_id)
        chunks = pdf_to_text(title, pages)
    else:
        return []

    # Store in cache
    _file_cache[file_id] = (now, chunks)
    return chunks[:max_chunks]


_ANALYTICS_SYSTEM_PROMPT = (
    "Bạn là Driftless Analytics — AI phân tích dữ liệu nội bộ công ty.\n\n"
    "Nguyên tắc:\n"
    "- Tính toán chính xác dựa trên số liệu thật\n"
    "- Trả lời súc tích, có số liệu cụ thể\n"
    "- Dùng emoji và format Markdown cho dễ đọc\n"
    "- Highlight những điểm cần chú ý (overdue, below target, overload)\n"
    "- Đưa ra nhận xét ngắn và gợi ý hành động nếu cần\n"
    "- Trả lời bằng tiếng Việt"
)

_KNOWLEDGE_SYSTEM_PROMPT = (
    "Bạn là Driftless. Trả lời bằng tiếng Việt, ngắn gọn, đúng trong phạm vi "
    "nội dung file đã đọc. Nếu thiếu dữ liệu thì nói rõ thiếu gì."
)


def _get_company_folder_id(company_id: str) -> str | None:
    """Get Drive folder ID for a company."""
    result = (
        supabase.table("companies")
        .select("drive_folder_id")
        .eq("company_id", company_id)
        .execute()
    )
    if result.data and result.data[0].get("drive_folder_id"):
        return result.data[0]["drive_folder_id"]
    return None


def answer_question(query: str, company_id: str = "pilot") -> str:
    """Answer question by searching and reading Drive files on-demand."""
    folder_id = _get_company_folder_id(company_id)

    try:
        files = search_drive_files(query, page_size=6, folder_id=folder_id)
    except Exception:
        files = []

    if not files:
        return (
            "Tôi chưa tìm thấy file phù hợp trên Drive. "
            "Bạn có thể nói rõ hơn tên file hoặc thư mục."
        )

    selected = files[:3]
    contexts = []
    used_names = []
    has_sheet = False

    for file_meta in selected:
        try:
            chunks = _read_file_chunks(file_meta, max_chunks=4)
            if not chunks:
                continue
            used_names.append(file_meta.get("name", "unknown"))
            if file_meta.get("mimeType") == "application/vnd.google-apps.spreadsheet":
                has_sheet = True
            contexts.append(
                f"=== FILE: {file_meta.get('name', '')} ({file_meta.get('mimeType', '')}) ===\n"
                + "\n\n".join(chunks)
            )
        except Exception:
            continue

    if not contexts:
        return (
            "Tôi đã tìm thấy file nhưng chưa đọc được nội dung. "
            "Hãy kiểm tra quyền share cho service account."
        )

    merged_context = "\n\n---\n\n".join(contexts)

    # Use analytics prompt if query is analytics-style and file contains sheet data
    if has_sheet and _is_analytics_query(query):
        system_prompt = _ANALYTICS_SYSTEM_PROMPT
        max_tokens = 1500
    else:
        system_prompt = _KNOWLEDGE_SYSTEM_PROMPT
        max_tokens = 1200

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Dữ liệu file:\n{merged_context}\n\nYêu cầu: {query}",
            }
        ],
    )

    file_list = ", ".join(used_names[:5])
    return f"(Đã đọc từ Drive: {file_list})\n\n{response.content[0].text}"

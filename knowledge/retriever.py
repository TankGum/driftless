from anthropic import Anthropic
from config import CLAUDE_API_KEY
from database.supabase import supabase

claude = Anthropic(api_key=CLAUDE_API_KEY)

_STOPWORDS = {
    "là", "và", "của", "có", "không", "tôi", "bạn", "cho", "về", "với",
    "từ", "trong", "a", "the", "of", "in", "for", "to", "by", "at", "on",
    "được", "này", "đó", "các", "một", "những", "theo", "khi", "đã", "sẽ",
}


def _title_matches_query(title: str, query: str) -> bool:
    """Check if document title has any significant word overlap with query."""
    query_words = set(query.lower().split()) - _STOPWORDS
    title_words = set(title.lower().split()) - _STOPWORDS
    return bool(query_words & title_words)


def search_knowledge(query: str, company_id: str = "pilot", top_k: int = 5) -> list[str]:
    """Tìm chunks liên quan nhất với câu hỏi"""
    result = (
        supabase.table("document_chunks")
        .select("content, document_id, documents(company_id, title)")
        .execute()
    )

    # Filter by company, keeping title metadata
    company_rows = [
        row for row in result.data
        if row.get("documents", {}).get("company_id") == company_id
    ]

    if not company_rows:
        return []

    # Pre-filter: prefer docs whose title overlaps with query words
    matching_rows = [
        r for r in company_rows
        if _title_matches_query(r.get("documents", {}).get("title", ""), query)
    ]

    # Fall back to all company rows if no title match
    filtered_rows = matching_rows if matching_rows else company_rows

    # Build chunks with document title context for better Haiku ranking
    chunks_with_meta = [
        (row.get("documents", {}).get("title", "Tài liệu"), row["content"])
        for row in filtered_rows
    ]

    chunks_text = "\n\n---\n\n".join(
        f"[Chunk {i+1} — Tài liệu: {title}]\n{content}"
        for i, (title, content) in enumerate(chunks_with_meta)
    )

    ranking_response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""Câu hỏi: {query}

Dưới đây là các đoạn tài liệu. Hãy trả về số thứ tự của {top_k} đoạn liên quan nhất với câu hỏi, cách nhau bằng dấu phẩy. Chỉ trả về số, không giải thích.

{chunks_text}""",
            }
        ],
    )

    try:
        indices_text = ranking_response.content[0].text.strip()
        indices = [
            int(x.strip()) - 1
            for x in indices_text.split(",")
            if x.strip().isdigit()
        ]
        all_contents = [content for _, content in chunks_with_meta]
        relevant_chunks = [all_contents[i] for i in indices if i < len(all_contents)]
        return relevant_chunks
    except Exception:
        return [content for _, content in chunks_with_meta[:top_k]]


def answer_question(query: str, company_id: str = "pilot") -> str:
    """Trả lời câu hỏi dựa trên knowledge base"""
    relevant_chunks = search_knowledge(query, company_id)

    if not relevant_chunks:
        return "Tôi chưa có tài liệu về vấn đề này. Vui lòng liên hệ quản lý để được hỗ trợ."

    context = "\n\n---\n\n".join(relevant_chunks)

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="""Bạn là Driftless — AI Agent nội bộ của công ty. Trả lời câu hỏi của nhân viên dựa trên tài liệu được cung cấp.

Nguyên tắc trả lời:
- Tổng hợp thông tin từ tài liệu thành câu trả lời mạch lạc, có cấu trúc rõ ràng
- Nếu tài liệu là dạng bảng/thông số, hãy diễn giải thành hướng dẫn dễ hiểu
- Liệt kê các bước theo thứ tự nếu là quy trình
- Nếu thiếu thông tin, chỉ rõ phần nào còn thiếu và gợi ý hỏi ai
- Trả lời bằng tiếng Việt, thân thiện như đồng nghiệp
- KHÔNG bịa thêm thông tin không có trong tài liệu""",
        messages=[
            {
                "role": "user",
                "content": f"""Tài liệu công ty:
{context}

Câu hỏi: {query}""",
            }
        ],
    )

    return response.content[0].text

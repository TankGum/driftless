from anthropic import Anthropic
from config import CLAUDE_API_KEY
from database.supabase import supabase
from knowledge.embedder import embed_query

claude = Anthropic(api_key=CLAUDE_API_KEY)


def search_knowledge(query: str, company_id: str = "pilot", top_k: int = 5) -> list[dict]:
    """Vector similarity search với re-ranking bằng Haiku.

    Trả về list[dict] với keys: content, title, source_id.
    """
    query_embedding = embed_query(query)
    fetch_k = top_k * 2  # Lấy nhiều hơn để re-rank

    result = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "filter_company_id": company_id,
        "match_count": fetch_k,
    }).execute()

    if not result.data:
        return []

    # Parse raw rows — RPC có thể trả về document_id và metadata
    chunks = []
    doc_ids = []
    for row in result.data:
        doc_id = row.get("document_id")
        if doc_id:
            doc_ids.append(doc_id)
        meta = row.get("metadata") or {}
        chunks.append({
            "content": row["content"],
            "document_id": doc_id,
            "source_id": meta.get("source_id", ""),
            "title": meta.get("title", ""),  # Có nếu indexer mới lưu title vào metadata
        })

    # Batch lookup titles từ documents table nếu document_id có sẵn
    if doc_ids:
        unique_ids = list({str(d) for d in doc_ids})
        try:
            docs_result = (
                supabase.table("documents")
                .select("id, title")
                .in_("id", unique_ids)
                .execute()
            )
            id_to_title = {str(d["id"]): d["title"] for d in docs_result.data}
            for chunk in chunks:
                if chunk.get("document_id") and not chunk["title"]:
                    chunk["title"] = id_to_title.get(str(chunk["document_id"]), "")
        except Exception:
            pass

    if len(chunks) <= top_k:
        return chunks

    return _rerank(query, chunks, top_k)


def _rerank(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Dùng Claude Haiku để chọn top_k chunks liên quan nhất."""
    numbered = "\n\n".join(
        f"[{i + 1}] {c['content'][:300]}" for i, c in enumerate(chunks)
    )
    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system="Bạn là hệ thống re-ranking. Chỉ trả về danh sách số, không giải thích.",
            messages=[{
                "role": "user",
                "content": (
                    f"Câu hỏi: {query}\n\n"
                    f"Các đoạn văn:\n{numbered}\n\n"
                    f"Chọn {top_k} đoạn liên quan nhất theo thứ tự giảm dần. "
                    f"Trả về chỉ số thứ tự cách nhau bằng dấu phẩy. Ví dụ: 2,5,1"
                ),
            }],
        )
        raw = resp.content[0].text.strip()
        indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
        ranked = [chunks[i] for i in indices if 0 <= i < len(chunks)]
        # Thêm các chunk chưa được chọn vào cuối để không mất data
        seen = set(indices)
        for i, c in enumerate(chunks):
            if i not in seen:
                ranked.append(c)
        return ranked[:top_k]
    except Exception:
        return chunks[:top_k]


def answer_question(query: str, company_id: str = "pilot") -> str:
    """Trả lời câu hỏi dựa trên knowledge base, có trích dẫn nguồn."""
    chunks = search_knowledge(query, company_id)

    if not chunks:
        return "Tôi chưa có tài liệu về vấn đề này. Vui lòng liên hệ quản lý để được hỗ trợ."

    # Build context với nhãn nguồn đánh số
    context_parts = []
    for i, chunk in enumerate(chunks):
        label = f"[Nguồn {i + 1}]"
        if chunk.get("title"):
            label += f" {chunk['title']}"
        context_parts.append(f"{label}\n{chunk['content']}")
    context = "\n\n---\n\n".join(context_parts)

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system="""Bạn là Driftless — AI Agent nội bộ của công ty.

Khi trả lời, hãy theo quy trình:
<reasoning>
1. Câu hỏi này đang hỏi về điều gì?
2. Tài liệu nào chứa thông tin liên quan?
3. Điểm chính cần đưa vào câu trả lời là gì?
</reasoning>

Sau phần reasoning, viết câu trả lời cuối cùng bằng tiếng Việt.

Nguyên tắc:
- Chỉ dùng thông tin có trong tài liệu được cung cấp
- Nếu thiếu thông tin, nêu rõ và gợi ý hỏi ai
- Thân thiện như đồng nghiệp
- KHÔNG bịa thêm thông tin""",
            messages=[{
                "role": "user",
                "content": f"Tài liệu công ty:\n{context}\n\nCâu hỏi: {query}",
            }],
        )
        answer = response.content[0].text

        # Thêm citation footer với tên nguồn không trùng lặp
        seen_titles: list[str] = []
        for chunk in chunks:
            t = chunk.get("title", "")
            if t and t not in seen_titles:
                seen_titles.append(t)
        if seen_titles:
            answer += "\n\n---\n📎 *Nguồn:* " + " · ".join(seen_titles)

        return answer
    except Exception:
        return "Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi của bạn."

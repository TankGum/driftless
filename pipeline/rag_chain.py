"""LCEL RAG chain — full pipeline from query to answer.

Pipeline steps:
  1. Query rewrite (Claude Haiku)
  2. Embed rewritten query (FastEmbed, local)
  3. Hybrid search (semantic + keyword FTS) → merge → top-20
  4. Cross-encoder rerank → top-5
  5. Retrieval Guard (score < 0.3 → refuse without calling Claude)
  6. Generate answer (Claude Sonnet, streaming-compatible)
  7. Format response with citations

Input schema:  {"query": str, "company_id": str, "chat_history": list[dict]}
Output schema: str (answer with citations)
"""
from __future__ import annotations

from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from pipeline.query_rewriter import rewrite_query
from pipeline.reranker import rerank
from pipeline.guards import retrieval_guard, NoRelevantDocError, NO_INFO_MESSAGE
from knowledge.embedder import embed_query
from database.supabase import supabase
from config import CLAUDE_API_KEY


# ── Step helpers ──────────────────────────────────────────────────────────────

def _rewrite(inputs: dict) -> dict:
    """Step 1: Rewrite query for better retrieval."""
    rewritten = rewrite_query(inputs["query"], inputs.get("chat_history", []))
    return {**inputs, "rewritten_query": rewritten}


def _embed_and_hybrid_search(inputs: dict) -> dict:
    """Steps 2-3: Embed + hybrid search (semantic + FTS) → merge top-20."""
    rewritten = inputs["rewritten_query"]
    company_id = inputs["company_id"]

    # --- Semantic search (pgvector) ---
    embedding = embed_query(rewritten)
    semantic_result = supabase.rpc("match_documents", {
        "query_embedding": embedding,
        "filter_company_id": company_id,
        "match_count": 20,
    }).execute()
    semantic_chunks = _normalize_chunks(semantic_result.data or [])

    # --- Keyword FTS search ---
    keyword_chunks: list[dict] = []
    try:
        kw_result = supabase.rpc("keyword_search_chunks", {
            "query_text": rewritten,
            "filter_company_id": company_id,
            "match_count": 20,
        }).execute()
        keyword_chunks = _normalize_chunks(kw_result.data or [])
    except Exception:
        # FTS RPC might not exist yet (before migration) — degrade gracefully
        pass

    merged = _merge_results(semantic_chunks, keyword_chunks, top_k=20)
    return {**inputs, "chunks": merged}


def _normalize_chunks(rows: list[dict]) -> list[dict]:
    """Normalize RPC result rows into uniform chunk dicts."""
    chunks = []
    for row in rows:
        meta = row.get("metadata") or {}
        chunks.append({
            "id": str(row.get("id", "")),
            "content": row.get("content", ""),
            "document_id": str(row.get("document_id", "")),
            "title": meta.get("title", row.get("title", "")),
            "source_id": meta.get("source_id", row.get("source_id", "")),
        })
    return chunks


def _merge_results(
    semantic: list[dict],
    keyword: list[dict],
    top_k: int = 20,
) -> list[dict]:
    """Merge semantic + keyword results, dedup by id, preserve order."""
    seen: dict[str, dict] = {}
    for chunk in semantic + keyword:
        cid = chunk.get("id", "")
        if cid and cid not in seen:
            seen[cid] = chunk
        elif not cid:
            # No id — include anyway (shouldn't happen with proper schema)
            seen[f"_no_id_{len(seen)}"] = chunk
    return list(seen.values())[:top_k]


def _rerank_chunks(inputs: dict) -> dict:
    """Step 4: Cross-encoder rerank → keep top-5."""
    chunks = inputs.get("chunks", [])
    if not chunks:
        return {**inputs, "ranked_chunks": []}
    ranked = rerank(inputs["rewritten_query"], chunks, top_k=5)
    return {**inputs, "ranked_chunks": ranked}


def _apply_guard(inputs: dict) -> dict:
    """Step 5: Retrieval Guard — raise if confidence too low."""
    chunks = inputs.get("ranked_chunks", [])
    try:
        retrieval_guard(chunks)
    except NoRelevantDocError:
        return {**inputs, "answer": NO_INFO_MESSAGE, "guard_blocked": True}
    return {**inputs, "guard_blocked": False}


def _generate(inputs: dict) -> dict:
    """Step 6: Generate answer with Claude Sonnet + citation."""
    if inputs.get("guard_blocked"):
        return inputs

    from anthropic import Anthropic
    client = Anthropic(api_key=CLAUDE_API_KEY)

    chunks = inputs["ranked_chunks"]
    query = inputs["query"]  # Use ORIGINAL query for generation
    chat_history = inputs.get("chat_history", [])

    # Build context with numbered source labels
    context_parts = []
    for i, chunk in enumerate(chunks):
        label = f"[Nguồn {i + 1}]"
        if chunk.get("title"):
            label += f" {chunk['title']}"
        context_parts.append(f"{label}\n{chunk['content']}")
    context = "\n\n---\n\n".join(context_parts)

    user_content = f"Tài liệu công ty:\n{context}\n\nCâu hỏi: {query}"
    messages = list(chat_history) + [{"role": "user", "content": user_content}]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system="""Bạn là Driftless — AI Agent nội bộ của công ty.

Nhiệm vụ: Trả lời câu hỏi DỰA TRÊN TÀI LIỆU ĐƯỢC CUNG CẤP.

Quy tắc bắt buộc:
- Chỉ dùng thông tin có trong tài liệu bên dưới
- Trích dẫn nguồn theo format [Nguồn 1], [Nguồn 2], ...
- Nếu tài liệu không đủ thông tin → nói rõ và gợi ý hỏi ai
- Viết bằng tiếng Việt, thân thiện như đồng nghiệp
- KHÔNG bịa hoặc suy đoán thông tin ngoài tài liệu""",
            messages=messages,
        )
        answer = response.content[0].text
    except Exception as e:
        answer = f"Xin lỗi, tôi gặp lỗi khi tạo câu trả lời: {e}"

    # Append citation footer
    titles = []
    for chunk in chunks:
        t = chunk.get("title", "")
        if t and t not in titles:
            titles.append(t)
    if titles:
        answer += "\n\n---\n📎 *Nguồn:* " + " · ".join(titles)

    return {**inputs, "answer": answer}


def _extract_answer(inputs: dict) -> str:
    """Final step: extract the answer string."""
    return inputs.get("answer", NO_INFO_MESSAGE)


# ── LCEL Chain ────────────────────────────────────────────────────────────────

rag_chain = (
    RunnableLambda(_rewrite).with_config({"run_name": "query_rewrite"})
    | RunnableLambda(_embed_and_hybrid_search).with_config({"run_name": "hybrid_search"})
    | RunnableLambda(_rerank_chunks).with_config({"run_name": "rerank"})
    | RunnableLambda(_apply_guard).with_config({"run_name": "retrieval_guard"})
    | RunnableLambda(_generate).with_config({"run_name": "generate"})
    | RunnableLambda(_extract_answer).with_config({"run_name": "format_response"})
).with_config({"run_name": "driftless_rag"})


def answer_with_rag(query: str, company_id: str, chat_history: list[dict] | None = None) -> str:
    """Convenience wrapper — synchronous call to the full RAG chain."""
    return rag_chain.invoke({"query": query, "company_id": company_id, "chat_history": chat_history or []})

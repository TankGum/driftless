"""Query rewriting step — uses Claude Haiku to expand the query with keywords.

This improves both semantic search and FTS precision without significant cost.
"""
import os
from anthropic import Anthropic
from config import CLAUDE_API_KEY

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=CLAUDE_API_KEY)
    return _client


def rewrite_query(query: str) -> str:
    """Rewrite user query to be more search-friendly.

    Returns the rewritten query string. Falls back to original query on error.
    """
    try:
        resp = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "Viết lại câu hỏi sau rõ ràng hơn, thêm từ khóa liên quan "
                "để tìm kiếm chính xác hơn trong tài liệu nội bộ công ty. "
                "Trả về chỉ câu hỏi đã viết lại, không giải thích."
            ),
            messages=[{"role": "user", "content": query}],
        )
        rewritten = resp.content[0].text.strip()
        return rewritten if rewritten else query
    except Exception:
        return query

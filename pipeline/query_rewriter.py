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


def rewrite_query(query: str, chat_history: list[dict] | None = None) -> str:
    """Rewrite user query to be more search-friendly.

    Uses the last 4 messages (2 turns) of chat_history to resolve pronouns
    ("nó", "đó", "cái đó") before rewriting. Falls back to original query on error.
    """
    try:
        recent_history = (chat_history or [])[-4:]
        messages = list(recent_history) + [{"role": "user", "content": query}]

        resp = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "Viết lại câu hỏi sau rõ ràng hơn, thêm từ khóa liên quan "
                "để tìm kiếm chính xác hơn trong tài liệu nội bộ công ty. "
                "Nếu câu hỏi dùng đại từ tham chiếu ('nó', 'đó', 'cái đó', 'của nó'), "
                "hãy thay bằng tên cụ thể dựa vào lịch sử hội thoại bên trên. "
                "Trả về chỉ câu hỏi đã viết lại, không giải thích."
            ),
            messages=messages,
        )
        rewritten = resp.content[0].text.strip()
        return rewritten if rewritten else query
    except Exception:
        return query

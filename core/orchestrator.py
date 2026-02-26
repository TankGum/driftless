import time

from anthropic import Anthropic
from config import CLAUDE_API_KEY
from knowledge.retriever import answer_question
from analytics.analyzer import analyze_query
from forecasting.responder import answer_forecast
from support.drafter import draft_document as _draft

claude = Anthropic(api_key=CLAUDE_API_KEY)
MAX_TURNS = 5

# ── Session memory ────────────────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
_SESSION_TTL = 1800   # 30 phút không hoạt động → xoá session
_MAX_HISTORY = 5      # Tối đa 5 cặp hỏi-đáp


def _user_key(user: dict) -> str:
    return str(user.get("telegram_id") or user.get("zalo_id") or "")


def _get_history(user_key: str) -> list[dict]:
    """Trả về lịch sử hội thoại. Xoá session nếu đã hết TTL."""
    if not user_key:
        return []
    session = _sessions.get(user_key)
    if not session:
        return []
    if time.time() - session["last_active"] > _SESSION_TTL:
        _sessions.pop(user_key, None)
        return []
    return list(session["messages"])


def _save_history(user_key: str, query: str, answer: str) -> None:
    """Lưu cặp hỏi-đáp mới, giữ tối đa _MAX_HISTORY cặp."""
    if not user_key:
        return
    existing = list(_sessions.get(user_key, {}).get("messages", []))
    # Giữ (_MAX_HISTORY - 1) cặp cũ để nhường chỗ cho cặp mới
    keep = (_MAX_HISTORY - 1) * 2
    trimmed = existing[-keep:] if len(existing) > keep else existing
    trimmed += [
        {"role": "user", "content": query},
        {"role": "assistant", "content": answer},
    ]
    _sessions[user_key] = {"messages": trimmed, "last_active": time.time()}

# ── Tools ─────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_knowledge",
        "description": (
            "Tìm kiếm thông tin trong tài liệu nội bộ công ty. "
            "Dùng khi hỏi về quy trình, hướng dẫn, chính sách, báo cáo, SOP."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Câu hỏi hoặc từ khóa cần tìm"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "analyze_data",
        "description": (
            "Phân tích dữ liệu thực tế: KPI, tiến độ dự án, "
            "hiệu suất nhóm, task overdue, số liệu hoàn thành."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Câu hỏi phân tích cụ thể"}
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_forecast",
        "description": "Dự báo rủi ro: deadline có kịp không, KPI có đạt không, ai đang bị quá tải.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Câu hỏi về dự báo"}
            },
            "required": ["question"],
        },
    },
    {
        "name": "draft_document",
        "description": "Soạn thảo tài liệu: status report, email client, meeting notes, handover.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "Yêu cầu soạn thảo cụ thể"}
            },
            "required": ["request"],
        },
    },
]

# ── Entry point ───────────────────────────────────────────────────────────────

def process(query: str, company_id: str, user: dict) -> str:
    """Entry point cho free-text messages — ReAct loop với short-term memory."""
    user_key = _user_key(user)
    history = _get_history(user_key)

    # Lịch sử + câu hỏi hiện tại
    messages = history + [{"role": "user", "content": query}]

    for _ in range(MAX_TURNS):
        try:
            response = claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=_system_prompt(user),
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            return f"Lỗi kết nối AI: {e}"

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    _save_history(user_key, query, block.text)
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _dispatch(block.name, block.input, company_id, user)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})

    # Fallback nếu vượt quá MAX_TURNS
    answer = answer_question(query, company_id)
    _save_history(user_key, query, answer)
    return answer


def _dispatch(name: str, inputs: dict, company_id: str, user: dict) -> str:
    try:
        if name == "search_knowledge":
            return answer_question(inputs["query"], company_id)
        if name == "analyze_data":
            return analyze_query(inputs["question"], company_id)
        if name == "get_forecast":
            return answer_forecast(inputs["question"], company_id)
        if name == "draft_document":
            return _draft(inputs["request"], user)
        return f"Tool '{name}' không tồn tại."
    except Exception as e:
        return f"Lỗi khi thực hiện {name}: {e}"


def _system_prompt(user: dict) -> str:
    role = (user or {}).get("role", "member")
    name = (user or {}).get("full_name") or (user or {}).get("username") or "bạn"
    return f"""Bạn là Driftless — AI Agent nội bộ của công ty.
Người dùng: {name} (vai trò: {role}).

Bạn có thể nhớ ngữ cảnh từ các tin nhắn trước trong cuộc hội thoại này.

Quy trình (ReAct):
1. Phân tích câu hỏi — cần thông tin gì?
2. Gọi tool phù hợp (có thể gọi nhiều tool theo thứ tự)
3. Đọc kết quả, quyết định có cần gọi thêm không
4. Tổng hợp câu trả lời mạch lạc bằng tiếng Việt

Chọn tool theo loại thông tin:
- Thông tin nội bộ công ty → search_knowledge
- Dữ liệu/số liệu thực tế công ty → analyze_data hoặc get_forecast
- Nếu không có thông tin trong tài liệu → trả lời "Tôi không có thông tin về vấn đề này trong tài liệu nội bộ."

Câu hỏi đơn giản (chào hỏi, hỏi về bản thân) → trả lời trực tiếp, không cần gọi tool."""

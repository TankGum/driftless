"""Central orchestrator — ReAct agent dùng ChatAnthropic.bind_tools() + LangSmith.

LangChain 1.x đã remove AgentExecutor. Dùng bind_tools() + manual loop thay thế.
LangSmith traces tự động khi LANGCHAIN_TRACING_V2=true trong .env.
API công khai: process(query, company_id, user) -> str — không thay đổi.
"""
import time
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from config import CLAUDE_API_KEY
from core.logger import logger

# ── Session memory ────────────────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
_SESSION_TTL = 1800   # 30 min idle → clear
_MAX_HISTORY = 5
MAX_TURNS = 5


def _user_key(user: dict) -> str:
    return str(user.get("telegram_id") or user.get("zalo_id") or "")


def _get_history(user_key: str) -> list:
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
    if not user_key:
        return
    existing = list(_sessions.get(user_key, {}).get("messages", []))
    keep = (_MAX_HISTORY - 1) * 2
    trimmed = existing[-keep:] if len(existing) > keep else existing
    trimmed += [HumanMessage(content=query), AIMessage(content=answer)]
    _sessions[user_key] = {"messages": trimmed, "last_active": time.time()}


# ── LangChain Tools ───────────────────────────────────────────────────────────

def _make_tools(company_id: str, user: dict) -> list:
    @tool
    def search_knowledge(query: str) -> str:
        """Tìm kiếm thông tin trong tài liệu nội bộ công ty.
        Dùng khi hỏi về quy trình, hướng dẫn, chính sách, báo cáo, SOP."""
        try:
            from pipeline.rag_chain import answer_with_rag
            return answer_with_rag(query, company_id)
        except Exception:
            from knowledge.retriever import answer_question
            return answer_question(query, company_id)

    @tool
    def analyze_data(question: str) -> str:
        """Phân tích dữ liệu thực tế: KPI, tiến độ dự án, hiệu suất nhóm,
        task overdue, số liệu hoàn thành."""
        from analytics.analyzer import analyze_query
        return analyze_query(question, company_id)

    @tool
    def get_forecast(question: str) -> str:
        """Dự báo rủi ro: deadline có kịp không, KPI có đạt không, ai đang bị quá tải."""
        from forecasting.responder import answer_forecast
        return answer_forecast(question, company_id)

    @tool
    def draft_document(request: str) -> str:
        """Soạn thảo tài liệu: status report, email client, meeting notes, handover."""
        from support.drafter import draft_document as _draft
        return _draft(request, user)

    return [search_knowledge, analyze_data, get_forecast, draft_document]


# ── ReAct loop ────────────────────────────────────────────────────────────────

def _run_react_loop(
    query: str,
    company_id: str,
    user: dict,
    history: list,
) -> str:
    role = (user or {}).get("role", "member")
    name = (user or {}).get("full_name") or (user or {}).get("username") or "bạn"

    system = SystemMessage(content=f"""Bạn là Driftless — AI Agent nội bộ của công ty.
Người dùng: {name} (vai trò: {role}).

Quy trình:
1. Phân tích câu hỏi — cần thông tin gì?
2. Gọi tool phù hợp (có thể gọi nhiều tool)
3. Tổng hợp câu trả lời bằng tiếng Việt

Chọn tool:
- Thông tin nội bộ → search_knowledge
- Số liệu/dữ liệu → analyze_data hoặc get_forecast
- Soạn thảo → draft_document
- Câu đơn giản (chào hỏi) → trả lời trực tiếp, không cần tool
- Không có thông tin → "Tôi không có thông tin về vấn đề này trong tài liệu nội bộ." """)

    tools = _make_tools(company_id, user)
    tool_map = {t.name: t for t in tools}

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=CLAUDE_API_KEY,
        max_tokens=2000,
        temperature=0,
    ).bind_tools(tools)

    messages = [system] + history + [HumanMessage(content=query)]

    for _ in range(MAX_TURNS):
        response = llm.invoke(
            messages,
            config={
                "run_name": "driftless_agent",
                "tags": [
                    f"company:{company_id}",
                    "telegram" if user.get("telegram_id") else "zalo",
                ],
                "metadata": {"company_id": company_id, "user_role": role},
            },
        )
        messages.append(response)

        # No tool calls → final answer
        if not response.tool_calls:
            return response.content or ""

        # Execute all tool calls
        for tc in response.tool_calls:
            fn = tool_map.get(tc["name"])
            try:
                result = fn.invoke(tc["args"]) if fn else f"Tool '{tc['name']}' không tồn tại."
            except Exception as e:
                result = f"Lỗi khi thực hiện {tc['name']}: {e}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    # Fallback nếu quá MAX_TURNS
    return messages[-1].content if hasattr(messages[-1], "content") else ""


# ── Public API ────────────────────────────────────────────────────────────────

def process(query: str, company_id: str, user: dict) -> str:
    """Entry point cho free-text messages — giữ nguyên signature cũ."""
    user_key = _user_key(user)
    history = _get_history(user_key)

    try:
        answer = _run_react_loop(query, company_id, user, history)
        if not answer:
            raise ValueError("Empty response")
        _save_history(user_key, query, answer)
        return answer
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        try:
            from pipeline.rag_chain import answer_with_rag
            answer = answer_with_rag(query, company_id)
        except Exception:
            from knowledge.retriever import answer_question
            answer = answer_question(query, company_id)
        _save_history(user_key, query, answer)
        return answer

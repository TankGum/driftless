"""Persistent chat history — single source of truth for all platforms.

user_key format:
  - Telegram:  telegram:{telegram_id}
  - Zalo:      zalo:{zalo_id}
  - Chainlit:  chainlit:{username}
"""
from database.supabase import supabase
from config import CHAT_HISTORY_MAX_TURNS


def load_history(company_id: str, user_key: str) -> list[dict]:
    """Load last N turns từ DB, trả về list[{"role", "content"}]."""
    if not user_key:
        return []
    result = (
        supabase.table("chat_messages")
        .select("role, content")
        .eq("company_id", company_id)
        .eq("user_key", user_key)
        .order("created_at", desc=True)
        .limit(CHAT_HISTORY_MAX_TURNS * 2)
        .execute()
    )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(result.data or [])]


def save_exchange(company_id: str, user_key: str, platform: str, user_msg: str, assistant_msg: str) -> None:
    """Lưu 1 lượt hỏi/đáp (2 rows) vào DB."""
    if not user_key:
        return
    supabase.table("chat_messages").insert([
        {"company_id": company_id, "user_key": user_key, "platform": platform, "role": "user",      "content": user_msg},
        {"company_id": company_id, "user_key": user_key, "platform": platform, "role": "assistant", "content": assistant_msg},
    ]).execute()


# ── Session management (Chainlit WebUI only) ──────────────────────────────────

def create_session(company_id: str, user_key: str, session_id: str | None = None) -> str:
    """Tạo session mới, trả về session_id (UUID).

    Nếu session_id được truyền vào (từ Chainlit thread_id), dùng làm primary key.
    """
    data: dict = {"company_id": company_id, "user_key": user_key}
    if session_id:
        data["id"] = session_id
    result = (
        supabase.table("chat_sessions")
        .insert(data)
        .execute()
    )
    return result.data[0]["id"]


def load_session_history(session_id: str) -> list[dict]:
    """Load messages của 1 session cụ thể."""
    result = (
        supabase.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return [{"role": r["role"], "content": r["content"]} for r in (result.data or [])]


def save_exchange_to_session(
    session_id: str, company_id: str, user_key: str,
    platform: str, user_msg: str, assistant_msg: str,
) -> None:
    """Lưu 1 lượt hỏi/đáp vào session cụ thể."""
    supabase.table("chat_messages").insert([
        {"company_id": company_id, "user_key": user_key, "platform": platform,
         "role": "user",      "content": user_msg,      "session_id": session_id},
        {"company_id": company_id, "user_key": user_key, "platform": platform,
         "role": "assistant", "content": assistant_msg, "session_id": session_id},
    ]).execute()


def list_sessions(company_id: str, user_key: str, limit: int = 5) -> list[dict]:
    """Lấy danh sách sessions gần đây (pinned first)."""
    result = (
        supabase.table("chat_sessions")
        .select("id, title, is_pinned, created_at")
        .eq("company_id", company_id)
        .eq("user_key", user_key)
        .order("is_pinned", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def pin_session(session_id: str, pinned: bool = True) -> None:
    """Toggle pin trạng thái của session."""
    supabase.table("chat_sessions").update({"is_pinned": pinned}).eq("id", session_id).execute()


def update_session_title(session_id: str, title: str) -> None:
    """Cập nhật title session từ tin nhắn đầu tiên."""
    supabase.table("chat_sessions").update({"title": title[:50]}).eq("id", session_id).execute()


def cleanup_old_sessions(retention_days: int | None = None) -> int:
    """Xóa sessions không pin cũ hơn retention_days. CASCADE xóa cả messages."""
    from datetime import datetime, timedelta, timezone
    from config import CHAT_SESSION_RETENTION_DAYS
    days = retention_days if retention_days is not None else CHAT_SESSION_RETENTION_DAYS
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        supabase.table("chat_sessions")
        .delete()
        .eq("is_pinned", False)
        .lt("created_at", cutoff)
        .execute()
    )
    return len(result.data or [])

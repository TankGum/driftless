"""Chainlit BaseDataLayer implementation backed by Supabase.

Maps:
  chat_sessions  → ThreadDict
  chat_messages  → StepDict (loaded on get_thread; writes are no-op — messages
                              are saved manually via save_exchange_to_session)
"""
from typing import Dict, List, Optional

from chainlit.data.base import BaseDataLayer
from chainlit.types import (
    ThreadDict,
    ThreadFilter,
    Pagination,
    PaginatedResponse,
    PageInfo,
)
from chainlit.step import StepDict
from chainlit.user import PersistedUser, User

from database.supabase import supabase
from config import DEFAULT_COMPANY_ID


class DriftlessDataLayer(BaseDataLayer):

    # ── Helpers ───────────────────────────────────────────────────────────
    def _company_id(self) -> str:
        from config import TENANT_ID
        return str(TENANT_ID) if TENANT_ID > 0 else (DEFAULT_COMPANY_ID or "pilot")

    def _username_from_user_id(self, user_id: str) -> Optional[str]:
        """Chainlit passes filters.userId = PersistedUser.id (DB UUID).
        Resolve it back to username so we can build the user_key."""
        result = (
            supabase.table("users")
            .select("username")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0]["username"] if result.data else None

    # ── User ──────────────────────────────────────────────────────────────
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        company_id = self._company_id()
        result = (
            supabase.table("users")
            .select("id, username, full_name, role, company_id")
            .eq("username", identifier)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        return PersistedUser(
            id=str(row["id"]),
            identifier=row["username"],
            display_name=row.get("full_name"),
            metadata={
                "role": row.get("role"),
                "company_id": row.get("company_id"),
            },
            createdAt="",
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        existing = await self.get_user(user.identifier)
        if existing:
            return existing
        company_id = self._company_id()
        metadata = user.metadata or {}
        try:
            supabase.table("users").insert({
                "username": user.identifier,
                "full_name": metadata.get("full_name") or user.identifier,
                "role": "admin",
                "company_id": company_id,
            }).execute()
        except Exception:
            pass  # duplicate key or race condition — fall through to re-lookup
        return await self.get_user(user.identifier)

    # ── Threads (= chat_sessions) ─────────────────────────────────────────
    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        _empty = PaginatedResponse(
            pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None),
            data=[],
        )
        company_id = self._company_id()

        # filters.userId is the UUID from PersistedUser.id — resolve to username
        user_id = filters.userId or ""
        if not user_id:
            return _empty

        username = self._username_from_user_id(user_id)
        if not username:
            return _empty

        user_key = f"chainlit:{username}"

        result = (
            supabase.table("chat_sessions")
            .select("id, title, is_pinned, created_at")
            .eq("company_id", company_id)
            .eq("user_key", user_key)
            .order("is_pinned", desc=True)
            .order("created_at", desc=True)
            .limit(pagination.first or 20)
            .execute()
        )

        threads: List[ThreadDict] = []
        for s in result.data or []:
            pin_icon = "📌 " if s["is_pinned"] else ""
            name = pin_icon + (s["title"] or "Cuộc trò chuyện")
            threads.append(
                ThreadDict(
                    id=s["id"],
                    createdAt=s["created_at"],
                    name=name,
                    userId=user_id,
                    userIdentifier=username,
                    tags=["pinned"] if s["is_pinned"] else [],
                    metadata={"is_pinned": s["is_pinned"], "company_id": company_id},
                    steps=[],
                    elements=[],
                )
            )

        return PaginatedResponse(
            pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None),
            data=threads,
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        s_result = (
            supabase.table("chat_sessions")
            .select("id, title, is_pinned, created_at, company_id, user_key")
            .eq("id", thread_id)
            .limit(1)
            .execute()
        )
        if not s_result.data:
            return None
        s = s_result.data[0]

        msgs = (
            supabase.table("chat_messages")
            .select("id, role, content, created_at")
            .eq("session_id", thread_id)
            .order("created_at", desc=False)
            .execute()
        ).data or []

        steps: List[StepDict] = []
        for msg in msgs:
            step_type = "user_message" if msg["role"] == "user" else "assistant_message"
            steps.append(
                StepDict(
                    id=str(msg["id"]),
                    threadId=thread_id,
                    type=step_type,
                    output=msg["content"],
                    createdAt=msg.get("created_at"),
                    name="User" if msg["role"] == "user" else "Driftless",
                )
            )

        identifier = s["user_key"].replace("chainlit:", "")
        pin_icon = "📌 " if s["is_pinned"] else ""
        return ThreadDict(
            id=s["id"],
            createdAt=s["created_at"],
            name=pin_icon + (s["title"] or "Cuộc trò chuyện"),
            userId=identifier,
            userIdentifier=identifier,
            tags=["pinned"] if s["is_pinned"] else [],
            metadata={"is_pinned": s["is_pinned"], "company_id": s["company_id"]},
            steps=steps,
            elements=[],
        )

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        updates: Dict = {}
        if name is not None:
            clean = name.replace("📌 ", "").strip()
            if clean:
                updates["title"] = clean[:50]
        if tags is not None:
            updates["is_pinned"] = "pinned" in tags
        if metadata and "is_pinned" in metadata:
            updates["is_pinned"] = metadata["is_pinned"]
        if updates:
            supabase.table("chat_sessions").update(updates).eq("id", thread_id).execute()

    async def delete_thread(self, thread_id: str):
        supabase.table("chat_sessions").delete().eq("id", thread_id).execute()

    async def get_thread_author(self, thread_id: str) -> str:
        result = (
            supabase.table("chat_sessions")
            .select("user_key")
            .eq("id", thread_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["user_key"].replace("chainlit:", "")
        return ""

    # ── Steps — no-op (messages saved manually in on_message) ─────────────
    async def create_step(self, step_dict: StepDict): pass
    async def update_step(self, step_dict: StepDict): pass
    async def delete_step(self, step_id: str): pass

    # ── Elements — no-op ──────────────────────────────────────────────────
    async def get_element(self, thread_id: str, element_id: str): return None
    async def create_element(self, element): pass
    async def delete_element(self, element_id: str, thread_id=None): pass

    # ── Feedback — no-op ──────────────────────────────────────────────────
    async def upsert_feedback(self, feedback): return ""
    async def delete_feedback(self, feedback_id: str) -> bool: return True

    # ── Misc — no-op ──────────────────────────────────────────────────────
    async def build_debug_url(self) -> str: return ""
    async def close(self): pass
    async def get_favorite_steps(self, user_id: str): return []

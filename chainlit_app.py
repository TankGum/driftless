"""Chainlit WebUI entry point — streaming chat interface for Driftless.

Run standalone:  chainlit run chainlit_app.py
Or mounted:      python main.py (FastAPI mounts Chainlit at /)
"""
import asyncio
import os
import tempfile
import httpx
import chainlit as cl

from pipeline.rag_chain import rag_chain, NO_INFO_MESSAGE
from pipeline.guards import NoRelevantDocError
from core.orchestrator import process as orchestrate
from core.chat_history import (
    load_history, save_exchange,
    create_session, load_session_history, save_exchange_to_session,
    list_sessions, pin_session, update_session_title,
)
from chainlit.types import ThreadDict
from core.logger import logger
from config import CHAT_HISTORY_MAX_TURNS


@cl.data_layer
def get_data_layer():
    from core.chainlit_data_layer import DriftlessDataLayer
    return DriftlessDataLayer()


# ── Auth ──────────────────────────────────────────────────────────────────────

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Authenticate via driftless portal email + password."""
    from config import PORTAL_URL, TENANT_ID

    if not PORTAL_URL or not TENANT_ID:
        return None

    try:
        resp = httpx.post(
            f"{PORTAL_URL}/api/v1/auth/login",
            json={"email": username, "password": password},
            timeout=10.0,
        )
    except httpx.RequestError:
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    access_token = data.get("tokens", {}).get("access_token")
    user_info = data.get("user", {})
    if not access_token:
        return None

    try:
        tenant_resp = httpx.get(
            f"{PORTAL_URL}/api/v1/tenants/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
    except httpx.RequestError:
        return None

    if tenant_resp.status_code != 200:
        return None

    tenant = tenant_resp.json()
    if tenant is None or tenant.get("id") != TENANT_ID:
        return None

    return cl.User(
        identifier=user_info.get("email", username),
        metadata={
            "role": user_info.get("role", "user"),
            "company_id": str(TENANT_ID),
            "tenant_id": TENANT_ID,
            "full_name": user_info.get("full_name") or username,
            "provider": "portal",
        },
    )


# ── Session setup ─────────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_start():
    """Khởi tạo phiên chat mới — dùng Chainlit thread_id làm session_id."""
    user = cl.user_session.get("user")

    role       = user.metadata.get("role", "member")           if user else "member"
    company_id = user.metadata.get("company_id", "pilot")      if user else "pilot"
    full_name  = user.metadata.get("full_name", user.identifier) if user else "khách"
    user_key   = f"chainlit:{user.identifier}"                  if user else ""

    # Dùng thread_id của Chainlit làm session_id để đồng bộ với data layer
    thread_id = cl.context.session.thread_id

    cl.user_session.set("company_id", company_id)
    cl.user_session.set("user_key", user_key)
    cl.user_session.set("session_id", thread_id)
    cl.user_session.set("session_title_set", False)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("user_dict", {
        "full_name": full_name,
        "username": user.identifier if user else "khách",
        "role": role,
        "company_id": company_id,
        "telegram_id": None,
        "zalo_id": None,
    })

    # Tạo session trong DB với ID = Chainlit thread_id
    await asyncio.to_thread(create_session, company_id, user_key, thread_id)

    upload_hint = (
        "\nHoặc **upload file** để thêm vào knowledge base."
        if role in {"admin", "pm"} else ""
    )
    pin_action = cl.Action(name="pin_session", payload={"action": "pin"}, label="📌 Pin cuộc trò chuyện này")
    await cl.Message(
        content=(
            f"Xin chào **{full_name}**! Tôi là **Driftless** — AI Agent nội bộ.\n\n"
            "Bạn có thể hỏi tôi về:\n"
            "- Quy trình, chính sách, tài liệu nội bộ\n"
            "- KPI, tiến độ dự án, hiệu suất nhóm\n"
            "- Dự báo deadline, risk alerts\n"
            "- Soạn thảo tài liệu"
            + upload_hint
        ),
        actions=[pin_action],
    ).send()


@cl.on_chat_resume
async def on_resume(thread: ThreadDict):
    """Khôi phục phiên chat khi user click vào session ở sidebar trái."""
    user = cl.user_session.get("user")

    role       = user.metadata.get("role", "member")           if user else "member"
    company_id = user.metadata.get("company_id", "pilot")      if user else "pilot"
    full_name  = user.metadata.get("full_name", user.identifier) if user else "khách"
    user_key   = f"chainlit:{user.identifier}"                  if user else ""

    session_id = thread["id"]
    is_pinned  = (thread.get("metadata") or {}).get("is_pinned", False)

    # Xây dựng chat_history từ steps của thread
    history = [
        {
            "role": "user" if s["type"] == "user_message" else "assistant",
            "content": s.get("output", ""),
        }
        for s in thread.get("steps", [])
        if s.get("type") in ("user_message", "assistant_message")
    ]

    cl.user_session.set("company_id", company_id)
    cl.user_session.set("user_key", user_key)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("session_title_set", True)
    cl.user_session.set("chat_history", history[-(CHAT_HISTORY_MAX_TURNS * 2):])
    cl.user_session.set("user_dict", {
        "full_name": full_name,
        "username": user.identifier if user else "khách",
        "role": role,
        "company_id": company_id,
        "telegram_id": None,
        "zalo_id": None,
    })

    if is_pinned:
        action = cl.Action(name="unpin_session", payload={"action": "unpin"}, label="📌 Bỏ pin cuộc trò chuyện")
    else:
        action = cl.Action(name="pin_session", payload={"action": "pin"}, label="📌 Pin cuộc trò chuyện này")

    await cl.Message(
        content=f"▶️ Tiếp tục cuộc trò chuyện. Hỏi thêm nhé, **{full_name}**!",
        actions=[action],
    ).send()


@cl.action_callback("pin_session")
async def on_pin_session(action: cl.Action):
    session_id = cl.user_session.get("session_id", "")
    if session_id:
        await asyncio.to_thread(pin_session, session_id, True)
        await cl.Message(content="📌 Đã đánh dấu cuộc trò chuyện này là quan trọng. Sẽ không bị tự xóa.").send()


@cl.action_callback("unpin_session")
async def on_unpin_session(action: cl.Action):
    session_id = cl.user_session.get("session_id", "")
    if session_id:
        await asyncio.to_thread(pin_session, session_id, False)
        await cl.Message(content="📌 Đã bỏ pin cuộc trò chuyện này.").send()


# ── File upload handling ──────────────────────────────────────────────────────

async def _handle_file_upload(elements: list, company_id: str):
    """Index uploaded files into the knowledge base."""
    import asyncio
    from knowledge.indexer import sync_local_file

    user_dict = cl.user_session.get("user_dict", {})
    if user_dict.get("role") not in {"admin", "pm"}:
        await cl.Message(
            content="⛔ Chỉ Admin/PM mới upload được tài liệu."
        ).send()
        return

    for element in elements:
        if not hasattr(element, "path") or not element.path:
            continue

        msg = cl.Message(content=f"⏳ Đang index **{element.name}**...")
        await msg.send()

        try:
            actor_id = user_dict.get("username", "chainlit")
            # Chạy trong thread riêng để tránh block event loop của Chainlit
            success, message, meta = await asyncio.to_thread(
                sync_local_file, element.path, company_id, actor_id, element.name
            )

            if not success and message == "DUPLICATE":
                existing_title = meta["title"]
                res = await cl.AskActionMessage(
                    content=(
                        f"⚠️ Nội dung này đã tồn tại trong **{existing_title}**.\n"
                        f"Bạn có muốn thay thế bằng file **{element.name}** không?"
                    ),
                    actions=[
                        cl.Action(name="yes", payload={"action": "replace"}, label="✅ Thay thế"),
                        cl.Action(name="no",  payload={"action": "keep"},    label="❌ Giữ lại"),
                    ],
                ).send()
                if res and res.get("name") == "yes":
                    success, message, _ = await asyncio.to_thread(
                        sync_local_file, element.path, company_id, actor_id, element.name, True
                    )
                    await cl.Message(content=message).send()
                else:
                    await cl.Message(content="↩️ Đã giữ lại tài liệu cũ.").send()
                    continue
            else:
                await cl.Message(content=message).send()
        except Exception as e:
            logger.error(f"File upload error: {e}", exc_info=True)
            await cl.Message(
                content=f"❌ Lỗi khi index **{element.name}**: {e}"
            ).send()


# ── Message handling ──────────────────────────────────────────────────────────

@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages with streaming."""
    company_id = cl.user_session.get("company_id", "pilot")
    user_dict = cl.user_session.get("user_dict", {})
    chat_history = cl.user_session.get("chat_history", [])
    user_key = cl.user_session.get("user_key", "")

    # Handle file uploads
    if message.elements:
        await _handle_file_upload(message.elements, company_id)
        if not message.content.strip():
            return

    query = message.content.strip()
    if not query:
        return

    # Plan/trial enforcement
    from core.plan import check_query_allowed, increment_query_count
    allowed, plan_msg = await asyncio.to_thread(check_query_allowed, company_id)
    if not allowed:
        await cl.Message(content=plan_msg).send()
        return

    # Stream response via RAG chain
    response_msg = cl.Message(content="")
    await response_msg.send()

    full_answer = ""
    try:
        async with cl.Step(name="Tìm kiếm tài liệu") as step:
            # Stream generation step by step
            async for chunk in rag_chain.astream(
                {"query": query, "company_id": company_id, "chat_history": chat_history}
            ):
                if isinstance(chunk, str):
                    full_answer += chunk
                    await response_msg.stream_token(chunk)

            if not full_answer:
                # Fallback: non-streaming invoke
                full_answer = rag_chain.invoke(
                    {"query": query, "company_id": company_id, "chat_history": chat_history}
                )
                await response_msg.update()

            step.output = f"Trả lời xong ({len(full_answer)} ký tự)"

        await response_msg.update()

    except NoRelevantDocError:
        full_answer = NO_INFO_MESSAGE
        response_msg.content = full_answer
        await response_msg.update()

    except Exception as e:
        logger.error(f"Chainlit message error: {e}", exc_info=True)
        # Fallback to orchestrator
        try:
            full_answer = orchestrate(query, company_id, user_dict)
            response_msg.content = full_answer
            await response_msg.update()
        except Exception as fallback_err:
            full_answer = "Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi. Vui lòng thử lại."
            response_msg.content = full_answer
            await response_msg.update()
            logger.error(f"Fallback orchestrator error: {fallback_err}")

    # Update in-session cache + persist to DB
    if full_answer:
        chat_history = chat_history + [
            {"role": "user", "content": query},
            {"role": "assistant", "content": full_answer},
        ]
        cl.user_session.set("chat_history", chat_history[-(CHAT_HISTORY_MAX_TURNS * 2):])

        session_id = cl.user_session.get("session_id", "")
        await asyncio.to_thread(
            save_exchange_to_session, session_id, company_id, user_key, "chainlit", query, full_answer
        )

        # Set title từ tin nhắn đầu tiên
        if not cl.user_session.get("session_title_set", False) and session_id:
            await asyncio.to_thread(update_session_title, session_id, query)
            cl.user_session.set("session_title_set", True)

        # Increment trial query count after successful answer
        await asyncio.to_thread(increment_query_count, company_id)

"""Chainlit WebUI entry point — streaming chat interface for Driftless.

Run standalone:  chainlit run chainlit_app.py
Or mounted:      python main.py (FastAPI mounts Chainlit at /)
"""
import os
import tempfile
import bcrypt
import chainlit as cl

from pipeline.rag_chain import rag_chain, NO_INFO_MESSAGE
from pipeline.guards import NoRelevantDocError
from core.orchestrator import process as orchestrate
from core.logger import logger


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


# ── Auth ──────────────────────────────────────────────────────────────────────

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Xác thực qua username + mật khẩu bcrypt trong Supabase."""
    from database.supabase import supabase
    from config import DEFAULT_COMPANY_ID

    company_id = DEFAULT_COMPANY_ID or "pilot"

    try:
        result = (
            supabase.table("users")
            .select("id, username, full_name, role, company_id, password_hash")
            .eq("username", username)
            .eq("company_id", company_id)
            .single()
            .execute()
        )
    except Exception:
        return None  # 0 hoặc >1 kết quả → từ chối

    user_row = result.data if result and result.data else None
    if not user_row or not user_row.get("password_hash"):
        return None  # Tài khoản chưa được cấp mật khẩu WebUI

    if not _verify_password(password, user_row["password_hash"]):
        return None

    return cl.User(
        identifier=user_row["username"],
        metadata={
            "role": user_row.get("role", "member"),
            "company_id": user_row.get("company_id", company_id),
            "full_name": user_row.get("full_name") or user_row["username"],
            "provider": "credentials",
        },
    )


# ── Session setup ─────────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_start():
    """Khởi tạo phiên chat — lấy role/company từ metadata đã xác thực."""
    user = cl.user_session.get("user")

    role       = user.metadata.get("role", "member")      if user else "member"
    company_id = user.metadata.get("company_id", "pilot") if user else "pilot"
    full_name  = user.metadata.get("full_name", user.identifier) if user else "khách"

    cl.user_session.set("company_id", company_id)
    cl.user_session.set("user_dict", {
        "full_name": full_name,
        "username": user.identifier if user else "khách",
        "role": role,
        "company_id": company_id,
        "telegram_id": None,
        "zalo_id": None,
    })

    upload_hint = (
        "\nHoặc **upload file** để thêm vào knowledge base."
        if role in {"admin", "pm"} else ""
    )
    await cl.Message(
        content=(
            f"Xin chào **{full_name}**! Tôi là **Driftless** — AI Agent nội bộ.\n\n"
            "Bạn có thể hỏi tôi về:\n"
            "- Quy trình, chính sách, tài liệu nội bộ\n"
            "- KPI, tiến độ dự án, hiệu suất nhóm\n"
            "- Dự báo deadline, risk alerts\n"
            "- Soạn thảo tài liệu"
            + upload_hint
        )
    ).send()


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

    # Handle file uploads
    if message.elements:
        await _handle_file_upload(message.elements, company_id)
        if not message.content.strip():
            return

    query = message.content.strip()
    if not query:
        return

    # Stream response via RAG chain
    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        async with cl.Step(name="Tìm kiếm tài liệu") as step:
            # Stream generation step by step
            full_answer = ""
            async for chunk in rag_chain.astream(
                {"query": query, "company_id": company_id}
            ):
                if isinstance(chunk, str):
                    full_answer += chunk
                    await response_msg.stream_token(chunk)

            if not full_answer:
                # Fallback: non-streaming invoke
                full_answer = rag_chain.invoke(
                    {"query": query, "company_id": company_id}
                )
                await response_msg.update()

            step.output = f"Trả lời xong ({len(full_answer)} ký tự)"

        await response_msg.update()

    except NoRelevantDocError:
        response_msg.content = NO_INFO_MESSAGE
        await response_msg.update()

    except Exception as e:
        logger.error(f"Chainlit message error: {e}", exc_info=True)
        # Fallback to orchestrator
        try:
            answer = orchestrate(query, company_id, user_dict)
            response_msg.content = answer
            await response_msg.update()
        except Exception as fallback_err:
            response_msg.content = (
                "Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi. Vui lòng thử lại."
            )
            await response_msg.update()
            logger.error(f"Fallback orchestrator error: {fallback_err}")

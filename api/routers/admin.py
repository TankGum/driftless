"""Admin API routes: manage data sources, roles, sync."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from api.deps import get_current_user, get_company_id
from knowledge.source_manager import add_source, remove_source, list_sources, resync_all_sources
from database.supabase import supabase

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin mới thực hiện được thao tác này.",
        )


def _require_pm_or_above(user: dict):
    if user.get("role") not in {"admin", "pm"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin/PM mới thực hiện được thao tác này.",
        )


# ── Data sources ──────────────────────────────────────────────────────────────

class AddSourceRequest(BaseModel):
    url: str


class RemoveSourceRequest(BaseModel):
    url: str


class OperationResponse(BaseModel):
    success: bool
    message: str


@router.post("/sources", response_model=OperationResponse)
async def add_doc_source(
    body: AddSourceRequest,
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    company_id = get_company_id(user)
    actor_id = str(user.get("telegram_id") or user.get("zalo_id") or "")
    success, message = add_source(body.url, company_id, actor_id)
    return OperationResponse(success=success, message=message)


@router.delete("/sources", response_model=OperationResponse)
async def remove_doc_source(
    body: RemoveSourceRequest,
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    company_id = get_company_id(user)
    success, message = remove_source(body.url, company_id)
    return OperationResponse(success=success, message=message)


@router.get("/sources")
async def list_doc_sources(user: dict = Depends(get_current_user)):
    _require_pm_or_above(user)
    company_id = get_company_id(user)
    result_text = list_sources(company_id)
    return {"sources": result_text}


@router.post("/sources/resync", response_model=OperationResponse)
async def resync_sources(user: dict = Depends(get_current_user)):
    _require_admin(user)
    company_id = get_company_id(user)
    message = resync_all_sources(company_id)
    return OperationResponse(success=True, message=message)


# ── Role management ───────────────────────────────────────────────────────────

class SetRoleRequest(BaseModel):
    username: str
    role: str


@router.post("/roles", response_model=OperationResponse)
async def set_role(
    body: SetRoleRequest,
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    if body.role not in {"admin", "pm", "member"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role không hợp lệ. Chọn: admin, pm, member",
        )
    result = (
        supabase.table("users")
        .update({"role": body.role})
        .eq("username", body.username.lstrip("@"))
        .execute()
    )
    if result.data:
        return OperationResponse(
            success=True, message=f"Đã set @{body.username} thành {body.role}"
        )
    return OperationResponse(
        success=False, message=f"Không tìm thấy @{body.username}"
    )


# ── Sync status ───────────────────────────────────────────────────────────────

@router.get("/sync-status")
async def sync_status(user: dict = Depends(get_current_user)):
    _require_pm_or_above(user)
    company_id = get_company_id(user)
    result = (
        supabase.table("data_sources")
        .select("title, source_id, last_synced, is_active")
        .eq("company_id", company_id)
        .eq("is_active", True)
        .execute()
    )
    return {"sources": result.data or []}

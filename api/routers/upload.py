"""POST /api/upload — ingest a document into the knowledge base."""
import tempfile
import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from pydantic import BaseModel

from api.deps import get_current_user, get_company_id
from knowledge.indexer import sync_local_file

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx"}
MAX_FILE_SIZE_MB = 500


class UploadResponse(BaseModel):
    success: bool
    message: str
    source_id: str = ""


@router.post("", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    replace: bool = Query(False, description="Thay thế nếu trùng nội dung với file khác tên"),
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in {"admin", "pm"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin/PM mới upload được tài liệu.",
        )

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng file không được hỗ trợ. Chấp nhận: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Tối đa {MAX_FILE_SIZE_MB}MB.",
        )

    company_id = get_company_id(user)
    actor_id = str(user.get("telegram_id") or user.get("zalo_id") or "")

    # Save to temp file and index via source_manager
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        success, message, meta = sync_local_file(tmp_path, company_id, actor_id, filename=file.filename or "", force_replace=replace)
        if not success and message == "DUPLICATE":
            existing_title = meta["title"]
            return UploadResponse(
                success=False,
                message=f"Nội dung này đã tồn tại trong '{existing_title}'. Thêm ?replace=true để thay thế.",
                source_id=meta["source_id"],
            )
        return UploadResponse(success=success, message=message)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

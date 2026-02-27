"""POST /api/chat — non-streaming REST endpoint."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.deps import get_current_user, get_company_id
from core.orchestrator import process as orchestrate

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
    company_id: str


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    company_id = get_company_id(user)
    answer = orchestrate(body.query, company_id, user)
    return ChatResponse(answer=answer, company_id=company_id)

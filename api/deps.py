"""FastAPI dependency injection: user authentication and company resolution."""
from typing import Optional
from fastapi import Request, HTTPException, status
from core.auth import get_user, get_user_by_zalo_id
from core.company import get_user_company


def get_current_user(request: Request) -> dict:
    """
    Resolve user from request context.

    Priority:
    1. X-User-Id header (Telegram/Zalo internal calls)
    2. X-Zalo-Id header (Zalo platform)
    3. Chainlit user session (set via cl.user_session)
    """
    telegram_id = request.headers.get("X-User-Id")
    zalo_id = request.headers.get("X-Zalo-Id")

    user: Optional[dict] = None
    if telegram_id:
        try:
            user = get_user(int(telegram_id))
        except (ValueError, TypeError):
            pass
    elif zalo_id:
        user = get_user_by_zalo_id(zalo_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng chưa xác thực. Vui lòng /start bot trước.",
        )
    return user


def get_company_id(user: dict) -> str:
    """Resolve company_id from user record, fallback to 'pilot'."""
    return user.get("company_id") or "pilot"

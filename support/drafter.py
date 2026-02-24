import json

from anthropic import Anthropic
from analytics.data_loader import load_project_progress
from config import CLAUDE_API_KEY

claude = Anthropic(api_key=CLAUDE_API_KEY)

DRAFT_TEMPLATES = {
    "status_report": "viết status report",
    "email_client": "viết email cho client",
    "meeting_notes": "viết meeting notes",
    "handover": "viết tài liệu bàn giao",
}


def detect_draft_type(text: str) -> str:
    text_lower = text.lower()
    for draft_type, keyword in DRAFT_TEMPLATES.items():
        if any(k in text_lower for k in keyword.split()):
            return draft_type
    return "general"


def draft_document(query: str, user: dict) -> str:
    tasks = load_project_progress()
    user_tasks = [
        t
        for t in tasks
        if user.get("full_name", "").lower() in t.get("Owner", "").lower()
        or user.get("username", "").lower() in t.get("Owner", "").lower()
    ]

    context = ""
    if user_tasks:
        context = f"\nTask của {user.get('full_name', 'user')}:\n"
        context += json.dumps(user_tasks, ensure_ascii=False, indent=2)

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="""Bạn là Driftless — AI hỗ trợ viết tài liệu chuyên nghiệp cho nhân viên.

Khi draft tài liệu:
- Dùng format phù hợp (có header, section rõ ràng)
- Điền thông tin thật từ context nếu có
- Đánh dấu [CẦN ĐIỀN] cho những chỗ cần user tự điền
- Ngắn gọn, chuyên nghiệp, dùng tiếng Việt
- Kết thúc bằng gợi ý chỉnh sửa nếu cần""",
        messages=[
            {
                "role": "user",
                "content": f"Thông tin người dùng: {user.get('full_name', 'Nhân viên')}, Role: {user.get('role', 'member')}{context}\n\nYêu cầu: {query}",
            }
        ],
    )

    return response.content[0].text

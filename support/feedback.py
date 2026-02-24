from anthropic import Anthropic
from config import CLAUDE_API_KEY
from database.supabase import supabase

claude = Anthropic(api_key=CLAUDE_API_KEY)


def categorize_feedback(content: str) -> str:
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": f"""Phân loại feedback này vào 1 trong 4 category: process, management, culture, other.
Chỉ trả về đúng 1 từ.

Feedback: {content}""",
            }
        ],
    )
    category = response.content[0].text.strip().lower()
    return category if category in ["process", "management", "culture"] else "other"


def submit_feedback(content: str, company_id: str = "pilot") -> bool:
    try:
        category = categorize_feedback(content)
        supabase.table("feedbacks").insert(
            {
                "company_id": company_id,
                "content": content,
                "category": category,
                "status": "new",
            }
        ).execute()
        return True
    except Exception:
        return False


def get_feedback_summary(company_id: str = "pilot") -> str:
    result = (
        supabase.table("feedbacks")
        .select("*")
        .eq("company_id", company_id)
        .eq("status", "new")
        .order("created_at", desc=True)
        .execute()
    )

    feedbacks = result.data
    if not feedbacks:
        return "Chưa có feedback mới nào."

    by_category = {}
    for fb in feedbacks:
        cat = fb.get("category", "other")
        by_category.setdefault(cat, []).append(fb["content"])

    category_emoji = {
        "process": "⚙️ Quy trình",
        "management": " Quản lý",
        "culture": " Văn hóa",
        "other": " Khác",
    }

    lines = [f" *Feedback mới ({len(feedbacks)} mục):*\n"]
    for cat, items in by_category.items():
        lines.append(f"*{category_emoji.get(cat, cat)}* ({len(items)})")
        for item in items[:3]:
            lines.append(
                f"• _{item[:100]}..._" if len(item) > 100 else f"• _{item}_"
            )
        lines.append("")

    return "\n".join(lines)

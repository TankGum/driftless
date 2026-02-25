from database.supabase import supabase
from knowledge.retriever import answer_question

ONBOARDING_STEPS = [
    {
        "step": 0,
        "title": " Chào mừng bạn đến với công ty!",
        "content": "Tôi là Driftless — AI Agent hỗ trợ bạn trong công việc hàng ngày.\n\nHãy cùng nhau hoàn thành onboarding nhé! Gõ /next để tiếp tục.",
        "question": None,
    },
    {
        "step": 1,
        "title": " Giới thiệu công ty",
        "content": None,
        "question": "Giới thiệu tổng quan về công ty, sứ mệnh và các phòng ban chính",
    },
    {
        "step": 2,
        "title": " Quy trình làm việc",
        "content": None,
        "question": "Quy trình làm việc hàng ngày, standup meeting, báo cáo tiến độ",
    },
    {
        "step": 3,
        "title": " Công cụ & Tool",
        "content": None,
        "question": "Các công cụ và tool công ty đang sử dụng, cách truy cập",
    },
    {
        "step": 4,
        "title": " Liên hệ & Hỗ trợ",
        "content": None,
        "question": "Khi cần hỗ trợ thì liên hệ ai, channel nào",
    },
    {
        "step": 5,
        "title": "✅ Onboarding hoàn thành!",
        "content": (
            "Bạn đã hoàn thành onboarding! \n\n"
            "Từ giờ bạn có thể:\n"
            "• Hỏi tôi bất cứ điều gì về công ty\n"
            "• Dùng /mytasks để xem task của bạn\n"
            "• Dùng /feedback để gửi feedback ẩn danh\n"
            "• Chat tự nhiên — tôi luôn sẵn sàng hỗ trợ!"
        ),
        "question": None,
    },
]


def get_onboarding_progress(telegram_id: int) -> dict:
    result = (
        supabase.table("onboarding_progress")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )
    return result.data[0] if result.data else None


def init_onboarding(telegram_id: int):
    if get_onboarding_progress(telegram_id):
        return

    supabase.table("onboarding_progress").insert(
        {
            "telegram_id": telegram_id,
            "step": 0,
            "completed_steps": [],
        }
    ).execute()


def get_current_step_content(telegram_id: int, company_id: str = "pilot") -> tuple[str, bool]:
    progress = get_onboarding_progress(telegram_id)
    if not progress:
        init_onboarding(telegram_id)
        progress = get_onboarding_progress(telegram_id)

    current_step = progress["step"]

    if current_step >= len(ONBOARDING_STEPS):
        return "✅ Bạn đã hoàn thành onboarding rồi!", True

    step_data = ONBOARDING_STEPS[current_step]
    if step_data["question"]:
        content = answer_question(step_data["question"], company_id)
    else:
        content = step_data["content"]

    is_last = current_step == len(ONBOARDING_STEPS) - 1
    message = f"*{step_data['title']}*\n\n{content}"
    if not is_last:
        message += "\n\n_Gõ /next để tiếp tục_"

    return message, is_last


def advance_onboarding(telegram_id: int) -> tuple[str, bool]:
    progress = get_onboarding_progress(telegram_id)
    if not progress:
        init_onboarding(telegram_id)
        progress = get_onboarding_progress(telegram_id)

    current_step = progress["step"]
    next_step = current_step + 1

    if next_step >= len(ONBOARDING_STEPS):
        supabase.table("onboarding_progress").update(
            {"completed_at": "now()"}
        ).eq("telegram_id", telegram_id).execute()
        return "✅ Onboarding đã hoàn thành!", True

    supabase.table("onboarding_progress").update(
        {"step": next_step}
    ).eq("telegram_id", telegram_id).execute()

    return get_current_step_content(telegram_id)


# --- Zalo variants (uses zalo_id instead of telegram_id) ---


def get_onboarding_progress_zalo(zalo_id: str) -> dict:
    result = (
        supabase.table("onboarding_progress")
        .select("*")
        .eq("zalo_id", zalo_id)
        .execute()
    )
    return result.data[0] if result.data else None


def init_onboarding_zalo(zalo_id: str):
    if get_onboarding_progress_zalo(zalo_id):
        return

    supabase.table("onboarding_progress").insert(
        {
            "zalo_id": zalo_id,
            "step": 0,
            "completed_steps": [],
        }
    ).execute()


def get_current_step_content_zalo(zalo_id: str, company_id: str = "pilot") -> tuple[str, bool]:
    progress = get_onboarding_progress_zalo(zalo_id)
    if not progress:
        init_onboarding_zalo(zalo_id)
        progress = get_onboarding_progress_zalo(zalo_id)

    current_step = progress["step"]

    if current_step >= len(ONBOARDING_STEPS):
        return "Ban da hoan thanh onboarding roi!", True

    step_data = ONBOARDING_STEPS[current_step]
    if step_data["question"]:
        content = answer_question(step_data["question"], company_id)
    else:
        content = step_data["content"]

    is_last = current_step == len(ONBOARDING_STEPS) - 1
    message = f"{step_data['title']}\n\n{content}"
    if not is_last:
        message += "\n\nGui 'next' de tiep tuc"

    return message, is_last


def advance_onboarding_zalo(zalo_id: str) -> tuple[str, bool]:
    progress = get_onboarding_progress_zalo(zalo_id)
    if not progress:
        init_onboarding_zalo(zalo_id)
        progress = get_onboarding_progress_zalo(zalo_id)

    current_step = progress["step"]
    next_step = current_step + 1

    if next_step >= len(ONBOARDING_STEPS):
        supabase.table("onboarding_progress").update(
            {"completed_at": "now()"}
        ).eq("zalo_id", zalo_id).execute()
        return "Onboarding da hoan thanh!", True

    supabase.table("onboarding_progress").update(
        {"step": next_step}
    ).eq("zalo_id", zalo_id).execute()

    return get_current_step_content_zalo(zalo_id)

import json

from anthropic import Anthropic
from analytics.data_loader import load_all_data
from config import CLAUDE_API_KEY

claude = Anthropic(api_key=CLAUDE_API_KEY)


def analyze_query(query: str, company_id: str = "pilot") -> str:
    """Phân tích câu hỏi analytics và trả lời dựa trên data thật"""
    data = load_all_data(company_id)

    data_context = json.dumps(data, ensure_ascii=False, indent=2)

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="""Bạn là Driftless Analytics — AI phân tích dữ liệu nội bộ công ty.

Bạn có quyền truy cập vào 3 nguồn dữ liệu:
- project_progress: tiến độ từng task (Task ID, Task Name, Owner, Start/End Date, Status, Completion %, Priority)
- kpi_tracking: theo dõi KPI (KPI Name, Target, Current, Achievement %, Owner, Status)  
- team_performance: hiệu suất thành viên (Team Member, Role, Assigned Tasks, Completed Tasks, Performance %)

Nguyên tắc:
- Tính toán chính xác dựa trên số liệu thật
- Trả lời súc tích, có số liệu cụ thể
- Dùng emoji và format Markdown cho dễ đọc
- Highlight những điểm cần chú ý (overdue, below target, overload)
- Đưa ra nhận xét ngắn và gợi ý hành động nếu cần
- Trả lời bằng tiếng Việt""",
        messages=[
            {
                "role": "user",
                "content": f"""Dữ liệu hiện tại:
{data_context}

Câu hỏi: {query}""",
            }
        ],
    )

    return response.content[0].text


def get_quick_summary() -> str:
    """Tạo summary tổng quan — dùng cho báo cáo tự động"""
    return analyze_query(
        "Tổng hợp nhanh tình trạng hiện tại: "
        "có bao nhiêu task đang chạy/overdue, "
        "KPI nào đang below target, "
        "ai đang có performance thấp nhất?"
    )

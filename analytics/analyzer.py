import json

from anthropic import Anthropic
from analytics.data_loader import load_all_data
from config import CLAUDE_API_KEY

claude = Anthropic(api_key=CLAUDE_API_KEY)

MAX_ROWS_PER_TAB = 200       # tối đa 200 dòng mỗi tab
MAX_CONTEXT_CHARS = 80_000   # tối đa ~20k tokens input


def _trim_data(data: dict) -> tuple[dict, list[str]]:
    """Giới hạn số dòng mỗi tab và cảnh báo nếu bị cắt."""
    warnings = []
    trimmed_sheets = {}
    for tab, rows in data.get("sheets", {}).items():
        if len(rows) > MAX_ROWS_PER_TAB:
            warnings.append(f"Tab '{tab}': hiển thị {MAX_ROWS_PER_TAB}/{len(rows)} dòng")
            trimmed_sheets[tab] = rows[:MAX_ROWS_PER_TAB]
        else:
            trimmed_sheets[tab] = rows

    trimmed = {**data, "sheets": trimmed_sheets}
    for key in ("project_progress", "kpi_tracking", "team_performance"):
        lst = trimmed.get(key, [])
        if len(lst) > MAX_ROWS_PER_TAB:
            warnings.append(f"'{key}': hiển thị {MAX_ROWS_PER_TAB}/{len(lst)} dòng")
            trimmed[key] = lst[:MAX_ROWS_PER_TAB]
    return trimmed, warnings


def analyze_query(query: str, company_id: str = "pilot") -> str:
    """Phân tích câu hỏi analytics và trả lời dựa trên data thật"""
    data = load_all_data(company_id)

    data, warnings = _trim_data(data)
    if warnings:
        print(f"  [Analytics] Giới hạn data: {'; '.join(warnings)}")

    other_sheets_context = []
    for tab_name, rows in data.get("sheets", {}).items():
        snippet = (
            json.dumps(rows[:3], ensure_ascii=False, indent=2)
            if rows
            else "Không có dữ liệu"
        )
        other_sheets_context.append(f"=== {tab_name} ===\n{snippet}")

    data_context = json.dumps(data, ensure_ascii=False, indent=2)
    if len(data_context) > MAX_CONTEXT_CHARS:
        data_context = data_context[:MAX_CONTEXT_CHARS] + "\n... [DỮ LIỆU BỊ CẮT BỚT DO QUÁ DÀI]"
        print(f"  [Analytics] data_context vượt {MAX_CONTEXT_CHARS} ký tự, đã truncate")

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="""Bạn là Driftless Analytics — AI phân tích dữ liệu nội bộ công ty.

Bạn có quyền truy cập vào tất cả các sheet đang được index cho company: project progress, KPI, team performance, và bất kỳ sheet khác nào đang được bật (ví dụ: budget, roadmap, backlog...). Claude sẽ xét toàn bộ dữ liệu được cung cấp để trả lời một câu hỏi analytics bất kỳ.

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
                "content": (
                    f"Dữ liệu hiện tại:\n{data_context}\n\n"
                    f"Các sheet bổ sung:\n"
                    + ('\n\n'.join(other_sheets_context) or 'Không có sheet bổ sung.')
                    + f"\n\nCâu hỏi: {query}"
                ),
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

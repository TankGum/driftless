import json

from anthropic import Anthropic
from config import CLAUDE_API_KEY
from forecasting.engine import (
    forecast_deadline_risk,
    forecast_kpi_miss,
    forecast_team_workload,
    get_full_forecast,
)

claude = Anthropic(api_key=CLAUDE_API_KEY)


def answer_forecast(query: str) -> str:
    """Trả lời câu hỏi dự báo"""
    forecast = get_full_forecast()
    forecast_context = json.dumps(forecast, ensure_ascii=False, indent=2)

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="""Bạn là Driftless Forecast — AI dự báo rủi ro cho tổ chức.

Bạn có dữ liệu dự báo gồm:
- deadline_risks: các task có nguy cơ trễ deadline
- kpi_risks: các KPI có nguy cơ miss target
- workload: tình trạng workload từng thành viên

Nguyên tắc:
- Trả lời trực tiếp vào câu hỏi, có số liệu cụ thể
- Ưu tiên highlight rủi ro cao nhất trước
- Đưa ra recommendation hành động cụ thể
- Format rõ ràng với emoji và Markdown
- Trả lời bằng tiếng Việt""",
        messages=[
            {
                "role": "user",
                "content": f"""Dữ liệu dự báo:
{forecast_context}

Câu hỏi: {query}""",
            }
        ],
    )

    return response.content[0].text


def get_risk_alert() -> str:
    """Tạo risk alert tự động — push hàng ngày"""
    forecast = get_full_forecast()

    high_risks = [t for t in forecast["deadline_risks"] if "" in t["risk_level"]]
    kpi_risks = [k for k in forecast["kpi_risks"] if "" in k["risk_level"]]
    overloaded = [m for m in forecast["workload"] if "" in m["status"]]

    if not high_risks and not kpi_risks and not overloaded:
        return None

    alert_parts = [f" *Daily Risk Alert* — {forecast['generated_at']}\n"]

    if high_risks:
        alert_parts.append(f"*⚠️ {len(high_risks)} task có nguy cơ trễ deadline:*")
        for t in high_risks[:3]:
            alert_parts.append(
                f"• {t['task']} ({t['owner']}) — "
                f"còn {t['days_remaining']} ngày, {t['completion']}% hoàn thành"
            )

    if kpi_risks:
        alert_parts.append(f"\n* {len(kpi_risks)} KPI dưới ngưỡng an toàn:*")
        for k in kpi_risks[:3]:
            alert_parts.append(
                f"• {k['kpi']} ({k['owner']}) — "
                f"đạt {k['achievement']}% target"
            )

    if overloaded:
        alert_parts.append(f"\n* {len(overloaded)} thành viên cần chú ý:*")
        for m in overloaded[:3]:
            alert_parts.append(
                f"• {m['member']} — performance {m['performance']}%, "
                f"còn {m['pending']} task pending"
            )

    return "\n".join(alert_parts)

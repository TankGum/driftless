import json

from anthropic import Anthropic
from config import CLAUDE_API_KEY
from forecasting.engine import get_full_forecast

claude = Anthropic(api_key=CLAUDE_API_KEY)

MAX_FORECAST_ITEMS = 50    # tối đa 50 items mỗi category
MAX_CONTEXT_CHARS = 30_000  # tối đa ~7.5k tokens input


def answer_forecast(query: str, company_id: str = "pilot") -> str:
    """Trả lời câu hỏi dự báo"""
    forecast = get_full_forecast(company_id)

    for key in ("deadline_risks", "kpi_risks", "workload"):
        if len(forecast.get(key, [])) > MAX_FORECAST_ITEMS:
            print(f"  [Forecast] '{key}': giới hạn còn {MAX_FORECAST_ITEMS} items")
            forecast[key] = forecast[key][:MAX_FORECAST_ITEMS]

    forecast_context = json.dumps(forecast, ensure_ascii=False, indent=2)
    if len(forecast_context) > MAX_CONTEXT_CHARS:
        forecast_context = forecast_context[:MAX_CONTEXT_CHARS] + "\n... [DỮ LIỆU BỊ CẮT BỚT DO QUÁ DÀI]"
        print(f"  [Forecast] forecast_context vượt {MAX_CONTEXT_CHARS} ký tự, đã truncate")

    try:
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
    except Exception as e:
        return f"Lỗi khi tạo dự báo: {e}"


def get_risk_alert() -> str:
    """Tạo risk alert tự động — push hàng ngày"""
    forecast = get_full_forecast()

    high_risks = [
        t for t in forecast["deadline_risks"]
        if "OVERDUE" in t["risk_level"] or "HIGH RISK" in t["risk_level"]
    ]
    kpi_risks = [k for k in forecast["kpi_risks"] if "HIGH" in k["risk_level"]]
    overloaded = [m for m in forecast["workload"] if "OVERLOADED" in m["status"]]

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

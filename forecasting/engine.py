from datetime import date, datetime
import unicodedata

from dateutil import parser as date_parser

from analytics.data_loader import load_all_data


def parse_date_safe(date_str: str):
    """Parse date safely; return None on errors."""
    if not date_str:
        return None
    try:
        return date_parser.parse(str(date_str)).date()
    except Exception:
        return None


def parse_float_safe(value: str) -> float:
    """Parse float safely."""
    try:
        return float(str(value).replace("%", "").replace(",", "").strip())
    except Exception:
        return 0.0


def _normalize_key(value: str) -> str:
    text = str(value or "").strip().lower().replace("_", " ")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _get_row_value(row: dict, aliases: list[str], default=""):
    if not row:
        return default

    normalized = {_normalize_key(k): v for k, v in row.items()}
    for alias in aliases:
        key = _normalize_key(alias)
        if key in normalized and normalized[key] not in [None, ""]:
            return normalized[key]
    return default


def forecast_deadline_risk(company_id: str = "pilot") -> list[dict]:
    """Forecast tasks at risk of missing deadline."""
    data = load_all_data(company_id)
    tasks = data.get("project_progress", [])
    today = date.today()
    risks = []

    for task in tasks:
        status = str(_get_row_value(task, ["status", "trang thai", "state"], "")).lower()
        if status in ["done", "completed", "hoan thanh"]:
            continue

        end_date = parse_date_safe(
            _get_row_value(task, ["end date", "due date", "deadline", "ngay ket thuc"], "")
        )
        start_date = parse_date_safe(
            _get_row_value(task, ["start date", "ngay bat dau"], "")
        )
        completion = parse_float_safe(
            _get_row_value(task, ["completion %", "progress %", "% complete", "tien do"], "0")
        )

        if not end_date:
            continue

        days_remaining = (end_date - today).days

        if start_date and start_date < today:
            total_days = (end_date - start_date).days or 1
            elapsed_days = (today - start_date).days
            expected_completion = (elapsed_days / total_days) * 100
            gap = expected_completion - completion
        else:
            gap = 0

        if days_remaining < 0:
            risk_level = "OVERDUE"
        elif days_remaining <= 3 and completion < 80:
            risk_level = "HIGH RISK"
        elif days_remaining <= 7 and gap > 20:
            risk_level = "MEDIUM RISK"
        elif gap > 30:
            risk_level = "MEDIUM RISK"
        else:
            risk_level = "ON TRACK"

        if risk_level != "ON TRACK":
            risks.append(
                {
                    "task": _get_row_value(task, ["task name", "task", "title", "ten cong viec"], "Unknown"),
                    "owner": _get_row_value(task, ["owner", "assignee", "nguoi phu trach"], "Unknown"),
                    "end_date": str(end_date),
                    "days_remaining": days_remaining,
                    "completion": completion,
                    "gap": round(gap, 1),
                    "risk_level": risk_level,
                    "priority": _get_row_value(task, ["priority", "muc do uu tien"], "Normal"),
                }
            )

    risk_order = {"OVERDUE": 0, "HIGH RISK": 1, "MEDIUM RISK": 2}
    risks.sort(key=lambda x: (risk_order.get(x["risk_level"], 3), x["days_remaining"]))
    return risks


def forecast_kpi_miss(company_id: str = "pilot") -> list[dict]:
    """Forecast KPIs that may miss target."""
    data = load_all_data(company_id)
    kpis = data.get("kpi_tracking", [])
    at_risk = []

    for kpi in kpis:
        status = str(_get_row_value(kpi, ["status", "trang thai"], "")).lower()
        if status in ["done", "completed"]:
            continue

        target = parse_float_safe(_get_row_value(kpi, ["target", "muc tieu"], "0"))
        current = parse_float_safe(_get_row_value(kpi, ["current", "actual", "hien tai"], "0"))
        achievement = parse_float_safe(
            _get_row_value(kpi, ["achievement %", "progress %", "ti le dat duoc"], "0")
        )

        if target == 0:
            continue

        if achievement == 0 and target > 0:
            achievement = (current / target) * 100

        if achievement < 60:
            risk_level = "HIGH RISK"
            recommendation = "Need immediate action; currently below 60% target"
        elif achievement < 80:
            risk_level = "MEDIUM RISK"
            recommendation = "Need close tracking; risk of missing target"
        else:
            continue

        at_risk.append(
            {
                "kpi": _get_row_value(kpi, ["kpi name", "kpi", "metric"], "Unknown"),
                "owner": _get_row_value(kpi, ["owner", "assignee", "nguoi phu trach"], "Unknown"),
                "target": target,
                "current": current,
                "achievement": round(achievement, 1),
                "risk_level": risk_level,
                "recommendation": recommendation,
            }
        )

    at_risk.sort(key=lambda x: x["achievement"])
    return at_risk


def forecast_team_workload(company_id: str = "pilot") -> list[dict]:
    """Forecast overloaded or underutilized team members."""
    data = load_all_data(company_id)
    members = data.get("team_performance", [])
    forecast = []

    for member in members:
        assigned = parse_float_safe(
            _get_row_value(member, ["assigned tasks", "tasks assigned", "task duoc giao"], "0")
        )
        completed = parse_float_safe(
            _get_row_value(member, ["completed tasks", "tasks completed", "task hoan thanh"], "0")
        )
        performance = parse_float_safe(
            _get_row_value(member, ["performance %", "efficiency %", "hieu suat"], "0")
        )

        if assigned == 0:
            continue

        pending = assigned - completed
        completion_rate = (completed / assigned * 100) if assigned > 0 else 0

        if performance < 60 or (pending > 5 and completion_rate < 50):
            status = "OVERLOADED / AT RISK"
            recommendation = "Consider redistributing tasks or adding support"
        elif performance < 80:
            status = "NEEDS ATTENTION"
            recommendation = "Monitor closely and check blockers"
        elif pending == 0:
            status = "AVAILABLE"
            recommendation = "Can take additional tasks"
        else:
            status = "ON TRACK"
            recommendation = "Working normally"

        forecast.append(
            {
                "member": _get_row_value(member, ["team member", "member", "name"], "Unknown"),
                "role": _get_row_value(member, ["role", "position", "vai tro"], "Unknown"),
                "assigned": int(assigned),
                "completed": int(completed),
                "pending": int(pending),
                "performance": performance,
                "status": status,
                "recommendation": recommendation,
            }
        )

    forecast.sort(key=lambda x: x["performance"])
    return forecast


def get_full_forecast(company_id: str = "pilot") -> dict:
    """Build full forecast payload."""
    return {
        "deadline_risks": forecast_deadline_risk(company_id),
        "kpi_risks": forecast_kpi_miss(company_id),
        "workload": forecast_team_workload(company_id),
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

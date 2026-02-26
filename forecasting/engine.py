import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil import parser as date_parser

from analytics.data_loader import load_all_data


def parse_date_safe(date_str: str):
    """Parse date an toàn, trả về None nếu lỗi"""
    if not date_str:
        return None
    try:
        return date_parser.parse(date_str).date()
    except Exception:
        return None


def parse_float_safe(value: str) -> float:
    """Parse float an toàn"""
    try:
        return float(str(value).replace("%", "").replace(",", "").strip())
    except Exception:
        return 0.0


def forecast_deadline_risk(data: dict) -> list[dict]:
    """
    Dự báo task nào có nguy cơ trễ deadline.
    Logic: dựa trên completion % hiện tại vs thời gian còn lại
    """
    tasks = data.get("project_progress", [])
    today = date.today()
    risks = []

    for task in tasks:
        status = task.get("Status", "").lower()
        if status in ["done", "completed", "hoàn thành"]:
            continue

        end_date = parse_date_safe(task.get("End Date", ""))
        start_date = parse_date_safe(task.get("Start Date", ""))
        completion = parse_float_safe(task.get("Completion %", "0"))

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
                    "task": task.get("Task Name", "Unknown"),
                    "owner": task.get("Owner", "Unknown"),
                    "end_date": str(end_date),
                    "days_remaining": days_remaining,
                    "completion": completion,
                    "gap": round(gap, 1),
                    "risk_level": risk_level,
                    "priority": task.get("Priority", "Normal"),
                }
            )

    risk_order = {"OVERDUE": 0, "HIGH RISK": 1, "MEDIUM RISK": 2}
    risks.sort(key=lambda x: (risk_order.get(x["risk_level"], 3), x["days_remaining"]))
    return risks


def forecast_kpi_miss(data: dict) -> list[dict]:
    """
    Dự báo KPI nào có nguy cơ miss target.
    Logic: dựa trên achievement % và trend
    """
    kpis = data.get("kpi_tracking", [])
    at_risk = []

    for kpi in kpis:
        status = kpi.get("Status", "").lower()
        if status in ["done", "completed"]:
            continue

        target = parse_float_safe(kpi.get("Target", "0"))
        current = parse_float_safe(kpi.get("Current", "0"))
        achievement = parse_float_safe(kpi.get("Achievement %", "0"))

        if target == 0:
            continue

        if achievement == 0 and target > 0:
            achievement = (current / target) * 100

        if achievement < 60:
            risk_level = "HIGH RISK"
            recommendation = "Cần action ngay, đang dưới 60% target"
        elif achievement < 80:
            risk_level = "MEDIUM RISK"
            recommendation = "Cần theo dõi sát, có nguy cơ miss target"
        else:
            continue

        at_risk.append(
            {
                "kpi": kpi.get("KPI Name", "Unknown"),
                "owner": kpi.get("Owner", "Unknown"),
                "target": target,
                "current": current,
                "achievement": round(achievement, 1),
                "risk_level": risk_level,
                "recommendation": recommendation,
            }
        )

    at_risk.sort(key=lambda x: x["achievement"])
    return at_risk


def forecast_team_workload(data: dict) -> list[dict]:
    """
    Dự báo ai đang overload / underutilized.
    Logic: dựa trên assigned vs completed tasks và performance %
    """
    members = data.get("team_performance", [])
    forecast = []

    for member in members:
        assigned = parse_float_safe(member.get("Assigned Tasks", "0"))
        completed = parse_float_safe(member.get("Completed Tasks", "0"))
        performance = parse_float_safe(member.get("Performance %", "0"))

        if assigned == 0:
            continue

        pending = assigned - completed
        completion_rate = (completed / assigned * 100) if assigned > 0 else 0

        if performance < 60 or (pending > 5 and completion_rate < 50):
            status = "OVERLOADED / AT RISK"
            recommendation = "Cân nhắc redistribute task hoặc support thêm"
        elif performance < 80:
            status = "NEEDS ATTENTION"
            recommendation = "Theo dõi và check blockers"
        elif pending == 0:
            status = "AVAILABLE"
            recommendation = "Có thể nhận thêm task"
        else:
            status = "ON TRACK"
            recommendation = "Đang ổn"

        forecast.append(
            {
                "member": member.get("Team Member", "Unknown"),
                "role": member.get("Role", "Unknown"),
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
    """Tổng hợp toàn bộ forecast"""
    data = load_all_data(company_id)
    return {
        "deadline_risks": forecast_deadline_risk(data),
        "kpi_risks": forecast_kpi_miss(data),
        "workload": forecast_team_workload(data),
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

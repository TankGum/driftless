from analytics.data_loader import load_project_progress
from datetime import date
from forecasting.engine import parse_date_safe


def _search_tasks(tasks, candidates):
    lower_candidates = [c.lower().strip() for c in candidates if c]
    matches = []
    for task in tasks:
        owner = task.get("Owner", "").lower().strip()
        if not owner:
            continue
        for candidate in lower_candidates:
            if candidate in owner or owner in candidate:
                matches.append(task)
                break
    return matches


def _format_missing(name_label, owners):
    owners_list = "\n".join([f"• {o}" for o in owners])
    return (
        f"Tôi không tìm thấy task nào cho *{name_label}*.\n\n"
        f"Tên trong hệ thống hiện có:\n{owners_list}\n\n"
        f"Bạn được ghi tên theo format nào trong Sheet?"
    )


def _format_tasks(name_label, tasks):
    today = date.today()
    lines = [f" *Tasks của {name_label}:*\n"]
    for task in tasks:
        status = task.get("Status", "")
        completion = task.get("Completion %", "0")
        end_date = parse_date_safe(task.get("End Date", ""))
        priority = task.get("Priority", "Normal")

        if end_date:
            days_left = (end_date - today).days
            if days_left < 0:
                deadline_str = f" Overdue {abs(days_left)} ngày"
            elif days_left == 0:
                deadline_str = " Hôm nay!"
            elif days_left <= 3:
                deadline_str = f" Còn {days_left} ngày"
            else:
                deadline_str = f" Còn {days_left} ngày"
        else:
            deadline_str = "Không có deadline"

        lines.append(
            f"*{task.get('Task Name', 'Unknown')}*\n"
            f"  Status: {status} | {completion}% hoàn thành\n"
            f"  Deadline: {deadline_str} | Priority: {priority}\n"
        )

    return "\n".join(lines)


def get_my_tasks(user: dict) -> str:
    tasks = load_project_progress()
    name = user.get("full_name", "")
    username = user.get("username", "")

    print(f"[DEBUG] Looking for tasks - full_name: '{name}', username: '{username}'")
    print(f"[DEBUG] All owners in sheet: {list(set(t.get('Owner', '') for t in tasks))}")

    matched = _search_tasks(tasks, [name, username])
    if not matched:
        owners = list(set(t.get("Owner", "") for t in tasks if t.get("Owner")))
        return _format_missing(name or username or "bạn", owners)

    return _format_tasks(name or username or "bạn", matched)


def get_tasks_by_name(name: str) -> str:
    tasks = load_project_progress()
    normalized = name or ""

    matched = _search_tasks(tasks, [normalized])
    if not matched:
        owners = list(set(t.get("Owner", "") for t in tasks if t.get("Owner")))
        return _format_missing(normalized or "tên được cung cấp", owners)

    return _format_tasks(normalized, matched)

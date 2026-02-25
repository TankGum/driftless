from database.supabase import supabase
from knowledge.sheets_reader import get_sheets_service, list_spreadsheets_in_folder


def _normalize(text: str) -> str:
    return str(text or "").strip().lower().replace("_", " ")


def _has_any(text: str, keywords: list[str]) -> bool:
    value = _normalize(text)
    return any(k in value for k in keywords)


def _classify_tab(tab: str, headers: list[str]) -> str | None:
    """Infer logical dataset from tab name first, then fallback to header hints."""
    tab_name = _normalize(tab)
    header_text = " ".join(_normalize(h) for h in headers)

    project_keys = ["project", "progress", "task", "deadline", "milestone"]
    kpi_keys = ["kpi", "okr", "metric", "target", "achievement"]
    team_keys = ["team", "member", "workload", "performance", "capacity"]

    if _has_any(tab_name, project_keys):
        return "project_progress"
    if _has_any(tab_name, kpi_keys):
        return "kpi_tracking"
    if _has_any(tab_name, team_keys):
        return "team_performance"

    if _has_any(header_text, project_keys):
        return "project_progress"
    if _has_any(header_text, kpi_keys):
        return "kpi_tracking"
    if _has_any(header_text, team_keys):
        return "team_performance"
    return None


def get_company_sheet_ids(company_id: str = "pilot") -> list[str]:
    """Lấy tất cả sheet IDs từ Drive folder của company"""
    result = (
        supabase.table("companies")
        .select("drive_folder_id")
        .eq("company_id", company_id)
        .execute()
    )
    if not result.data or not result.data[0].get("drive_folder_id"):
        return []

    folder_id = result.data[0]["drive_folder_id"]
    files = list_spreadsheets_in_folder(folder_id)
    return [f["id"] for f in files]


def load_sheet_data(sheet_name: str, company_id: str = "pilot") -> list[dict]:
    """Tìm và đọc sheet theo tên từ tất cả sheet files trong Drive folder"""
    service = get_sheets_service()
    sheet_ids = get_company_sheet_ids(company_id)

    for sheet_id in sheet_ids:
        try:
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=sheet_name)
                .execute()
            )

            rows = result.get("values", [])
            if not rows:
                continue

            headers = rows[0]
            return [
                dict(zip(headers, row + [""] * (len(headers) - len(row))))
                for row in rows[1:]
            ]
        except Exception:
            continue

    return []


def load_project_progress(company_id: str = "pilot") -> list[dict]:
    data = load_all_data(company_id)
    return data.get("project_progress", [])


def load_kpi_tracking(company_id: str = "pilot") -> list[dict]:
    data = load_all_data(company_id)
    return data.get("kpi_tracking", [])


def load_team_performance(company_id: str = "pilot") -> list[dict]:
    data = load_all_data(company_id)
    return data.get("team_performance", [])


def load_all_data(company_id: str = "pilot") -> dict:
    """Load toàn bộ data từ tất cả sheets trong Drive folder của company"""
    service = get_sheets_service()
    sheet_ids = get_company_sheet_ids(company_id)

    sheets_map = {}
    project_progress = []
    kpi_tracking = []
    team_performance = []

    for sheet_id in sheet_ids:
        try:
            spreadsheet = (
                service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            )
            tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

            for tab in tabs:
                result = (
                    service.spreadsheets()
                    .values()
                    .get(spreadsheetId=sheet_id, range=tab)
                    .execute()
                )

                rows = result.get("values", [])
                if not rows:
                    continue

                headers = rows[0]
                data = [
                    dict(zip(headers, row + [""] * (len(headers) - len(row))))
                    for row in rows[1:]
                ]

                sheets_map.setdefault(tab, []).extend(data)

                bucket = _classify_tab(tab, headers)
                if bucket == "project_progress":
                    project_progress.extend(data)
                elif bucket == "kpi_tracking":
                    kpi_tracking.extend(data)
                elif bucket == "team_performance":
                    team_performance.extend(data)
        except Exception as e:
            print(f"Error loading sheet {sheet_id}: {e}")
            continue

    return {
        "sheets": sheets_map,
        "project_progress": project_progress,
        "kpi_tracking": kpi_tracking,
        "team_performance": team_performance,
    }

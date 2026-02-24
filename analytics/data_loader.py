from database.supabase import supabase
from knowledge.sheets_reader import get_sheets_service


def get_active_sheet_ids(company_id: str = "pilot") -> list[str]:
    """Lấy tất cả sheet IDs đang active từ DB"""
    result = (
        supabase.table("data_sources")
        .select("source_id")
        .eq("company_id", company_id)
        .eq("source_type", "google_sheets")
        .eq("is_active", True)
        .execute()
    )
    return [row["source_id"] for row in result.data]


def load_sheet_data(sheet_name: str, company_id: str = "pilot") -> list[dict]:
    """Tìm và đọc sheet theo tên từ tất cả sheet files đang active"""
    service = get_sheets_service()
    sheet_ids = get_active_sheet_ids(company_id)

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
    return load_sheet_data("Project Progress", company_id)


def load_kpi_tracking(company_id: str = "pilot") -> list[dict]:
    return load_sheet_data("KPI Tracking", company_id)


def load_team_performance(company_id: str = "pilot") -> list[dict]:
    return load_sheet_data("Team Performance", company_id)


def load_all_data(company_id: str = "pilot") -> dict:
    """Load toàn bộ data từ tất cả sheets đang active"""
    service = get_sheets_service()
    sheet_ids = get_active_sheet_ids(company_id)

    all_data = {
        "project_progress": [],
        "kpi_tracking": [],
        "team_performance": [],
        "other_sheets": {},
    }

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

                tab_lower = tab.lower()
                if "project" in tab_lower or "progress" in tab_lower:
                    all_data["project_progress"].extend(data)
                elif "kpi" in tab_lower:
                    all_data["kpi_tracking"].extend(data)
                elif "team" in tab_lower or "performance" in tab_lower:
                    all_data["team_performance"].extend(data)
                else:
                    all_data["other_sheets"][tab] = data
        except Exception as e:
            print(f"Error loading sheet {sheet_id}: {e}")
            continue

    return all_data

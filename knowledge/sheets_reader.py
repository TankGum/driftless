from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import GOOGLE_CREDENTIALS_PATH

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def get_sheets_service():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def get_docs_service():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("docs", "v1", credentials=creds)


def get_drive_service():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def read_sheet(sheet_id: str, range_name: str = None) -> list[dict]:
    """Đọc toàn bộ một sheet, trả về list of dicts"""
    service = get_sheets_service()

    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()

    all_data = []
    sheets = spreadsheet.get("sheets", [])

    for sheet in sheets:
        sheet_name = sheet["properties"]["title"]

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=sheet_name,
        ).execute()

        rows = result.get("values", [])
        if not rows:
            continue

        headers = rows[0]
        for i, row in enumerate(rows[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            row_dict = dict(zip(headers, padded))
            row_dict["_sheet_name"] = sheet_name
            row_dict["_row_number"] = i
            all_data.append(row_dict)

    return all_data


def sheet_to_text(rows: list[dict]) -> list[str]:
    """Convert rows thành text chunks để index"""
    chunks = []
    current_sheet = None
    current_chunk = []

    for row in rows:
        sheet_name = row.get("_sheet_name", "")

        if sheet_name != current_sheet:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_sheet = sheet_name
            current_chunk = [f"=== {sheet_name} ==="]

        row_text = " | ".join(
            [f"{k}: {v}" for k, v in row.items() if not k.startswith("_") and v]
        )

        if row_text.strip():
            current_chunk.append(row_text)

        if len(current_chunk) >= 20:
            chunks.append("\n".join(current_chunk))
            current_chunk = [f"=== {sheet_name} (tiếp) ==="]

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def read_doc(doc_id: str) -> list[dict]:
    """Đọc nội dung Google Doc, trả về list of dicts theo từng section"""
    service = get_docs_service()
    doc = service.documents().get(documentId=doc_id).execute()

    title = doc.get("title", "Untitled")
    content = doc.get("body", {}).get("content", [])

    chunks = []
    current_heading = title
    current_lines = []

    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")

        text = "".join(
            [
                el.get("textRun", {}).get("content", "")
                for el in paragraph.get("elements", [])
            ]
        ).strip()

        if not text:
            continue

        if "HEADING" in style:
            if current_lines:
                chunks.append(
                    {
                        "_sheet_name": title,
                        "_heading": current_heading,
                        "_content": "\n".join(current_lines),
                        "_row_number": len(chunks),
                    }
                )
            current_heading = text
            current_lines = []
        else:
            current_lines.append(text)

    if current_lines:
        chunks.append(
            {
                "_sheet_name": title,
                "_heading": current_heading,
                "_content": "\n".join(current_lines),
                "_row_number": len(chunks),
            }
        )

    return chunks


def doc_to_text(chunks: list[dict]) -> list[str]:
    """Convert doc chunks thành text để index"""
    result = []
    for chunk in chunks:
        heading = chunk.get("_heading", "")
        content = chunk.get("_content", "")
        sheet = chunk.get("_sheet_name", "")

        if content.strip():
            result.append(f"=== {sheet} — {heading} ===\n{content}")

    return result


def list_drive_files(folder_id: str = None) -> list[dict]:
    """List tất cả Google Docs và Sheets trong Drive (hoặc trong folder)"""
    service = get_drive_service()

    query = "mimeType='application/vnd.google-apps.document' or mimeType='application/vnd.google-apps.spreadsheet'"
    if folder_id:
        query = f"'{folder_id}' in parents and ({query})"

    result = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
    ).execute()

    return result.get("files", [])

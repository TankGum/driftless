from io import BytesIO

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import GOOGLE_CREDENTIALS_PATH

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def get_sheets_service():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def get_docs_service():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    return build("docs", "v1", credentials=creds)


def get_drive_service():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def get_drive_file_meta(file_id: str) -> dict:
    service = get_drive_service()
    return (
        service.files()
        .get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime",
            supportsAllDrives=True,
        )
        .execute()
    )


def search_drive_files(prompt: str, page_size: int = 8, folder_id: str = None) -> list[dict]:
    """Search docs/sheets/pdf by prompt text in Drive, optionally scoped to a folder."""
    import re

    service = get_drive_service()
    stop_words = {
        "file", "drive", "docs", "sheets", "pdf",
        "tìm", "tim", "cho", "tôi", "toi", "của", "cua",
        "trong", "một", "mot", "thế", "the", "nào", "nao",
        "như", "nhu", "bạn", "ban", "hãy", "hay", "với", "voi",
        "được", "duoc", "không", "khong", "lên", "len",
        "lấy", "lay", "đọc", "doc", "xem", "mở", "mo",
        "tải", "tai", "trên", "tren", "từ", "tu",
        "phân", "phan", "tích", "tich",
    }
    terms = [
        t
        for t in re.findall(r"[\w.-]{2,}", prompt or "", re.UNICODE)
        if t.lower() not in stop_words
    ][:6]

    file_mime_filter = (
        "mimeType='application/vnd.google-apps.document' "
        "or mimeType='application/vnd.google-apps.spreadsheet' "
        "or mimeType='application/pdf'"
    )

    folder_prefix = f"'{folder_id}' in parents and " if folder_id else ""

    all_files: list[dict] = []
    seen_ids: set[str] = set()

    # 1) Search for matching folders, then list files inside them
    if terms:
        safe_terms = [t.replace("'", "") for t in terms]
        folder_name_filter = " or ".join([f"name contains '{t}'" for t in safe_terms])
        folder_q = (
            f"{folder_prefix}mimeType='application/vnd.google-apps.folder' "
            f"and ({folder_name_filter}) and trashed=false"
        )
        try:
            folder_result = (
                service.files()
                .list(
                    q=folder_q,
                    fields="files(id, name)",
                    pageSize=5,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            for folder in folder_result.get("files", []):
                child_q = (
                    f"'{folder['id']}' in parents "
                    f"and ({file_mime_filter}) and trashed=false"
                )
                child_result = (
                    service.files()
                    .list(
                        q=child_q,
                        fields="files(id, name, mimeType, modifiedTime)",
                        orderBy="modifiedTime desc",
                        pageSize=page_size,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                for f in child_result.get("files", []):
                    if f["id"] not in seen_ids:
                        seen_ids.add(f["id"])
                        all_files.append(f)
        except Exception:
            pass

    # 2) Search files by name directly
    if terms:
        safe_terms = [t.replace("'", "") for t in terms]
        name_filter = " or ".join([f"name contains '{t}'" for t in safe_terms])
        q = f"{folder_prefix}({file_mime_filter}) and ({name_filter}) and trashed=false"
    else:
        q = f"{folder_prefix}({file_mime_filter}) and trashed=false"

    result = (
        service.files()
        .list(
            q=q,
            fields="files(id, name, mimeType, modifiedTime)",
            orderBy="modifiedTime desc",
            pageSize=page_size,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    for f in result.get("files", []):
        if f["id"] not in seen_ids:
            seen_ids.add(f["id"])
            all_files.append(f)

    # 3) Search by file content (fullText) if name search found few results
    if terms and len(all_files) < page_size:
        try:
            safe_terms = [t.replace("'", "") for t in terms]
            ft_filter = " or ".join([f"fullText contains '{t}'" for t in safe_terms])
            ft_q = f"{folder_prefix}({file_mime_filter}) and ({ft_filter}) and trashed=false"
            ft_result = (
                service.files()
                .list(
                    q=ft_q,
                    fields="files(id, name, mimeType, modifiedTime)",
                    orderBy="modifiedTime desc",
                    pageSize=page_size,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            for f in ft_result.get("files", []):
                if f["id"] not in seen_ids:
                    seen_ids.add(f["id"])
                    all_files.append(f)
        except Exception:
            pass

    return all_files[:page_size]


def read_sheet(sheet_id: str, range_name: str = None) -> list[dict]:
    """Read all tabs from a Google Sheet and return row dicts."""
    service = get_sheets_service()

    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    all_data = []
    sheets = spreadsheet.get("sheets", [])

    for sheet in sheets:
        sheet_name = sheet["properties"]["title"]
        target_range = range_name or sheet_name

        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=target_range)
            .execute()
        )

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
    """Convert sheet rows to text chunks for indexing."""
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

        row_text = " | ".join([f"{k}: {v}" for k, v in row.items() if not k.startswith("_") and v])

        if row_text.strip():
            current_chunk.append(row_text)

        if len(current_chunk) >= 20:
            chunks.append("\n".join(current_chunk))
            current_chunk = [f"=== {sheet_name} (tiếp) ==="]

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def read_doc(doc_id: str) -> list[dict]:
    """Read Google Doc content and split by headings."""
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
        text = "".join([el.get("textRun", {}).get("content", "") for el in paragraph.get("elements", [])]).strip()

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
    """Convert doc chunks to text chunks for indexing."""
    result = []
    for chunk in chunks:
        heading = chunk.get("_heading", "")
        content = chunk.get("_content", "")
        sheet = chunk.get("_sheet_name", "")

        if content.strip():
            result.append(f"=== {sheet} — {heading} ===\n{content}")

    return result


def read_pdf(file_id: str) -> tuple[str, list[str]]:
    """Read PDF from Drive and return (title, extracted_pages)."""
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError("Thiếu thư viện pypdf. Hãy cài dependencies mới để đọc PDF.") from e

    service = get_drive_service()
    meta = get_drive_file_meta(file_id)
    raw_bytes = service.files().get_media(fileId=file_id).execute()

    reader = PdfReader(BytesIO(raw_bytes))
    pages = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(text)

    return meta.get("name", file_id), pages


def pdf_to_text(title: str, pages: list[str], max_chars: int = 2500) -> list[str]:
    """Convert PDF pages to chunks for indexing."""
    chunks = []
    current = []
    current_len = 0

    for idx, page_text in enumerate(pages, start=1):
        block = f"[Trang {idx}]\n{page_text}"
        if current_len + len(block) > max_chars and current:
            chunks.append(f"=== {title} ===\n" + "\n\n".join(current))
            current = []
            current_len = 0

        current.append(block)
        current_len += len(block)

    if current:
        chunks.append(f"=== {title} ===\n" + "\n\n".join(current))

    return chunks


def list_spreadsheets_in_folder(folder_id: str) -> list[dict]:
    """List all spreadsheets in a Drive folder."""
    service = get_drive_service()
    q = (
        f"'{folder_id}' in parents "
        f"and mimeType='application/vnd.google-apps.spreadsheet' "
        f"and trashed=false"
    )
    result = (
        service.files()
        .list(
            q=q,
            fields="files(id, name, mimeType, modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    return result.get("files", [])


def list_drive_files(folder_id: str = None) -> list[dict]:
    """List Google Docs, Sheets, and PDFs in Drive (or in a folder)."""
    service = get_drive_service()

    query = (
        "mimeType='application/vnd.google-apps.document' "
        "or mimeType='application/vnd.google-apps.spreadsheet' "
        "or mimeType='application/pdf'"
    )
    if folder_id:
        query = f"'{folder_id}' in parents and ({query})"

    result = (
        service.files()
        .list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    return result.get("files", [])

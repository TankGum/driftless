import io

import pypdf
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

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


def get_sheet_title(sheet_id: str) -> str:
    """Lấy tên thực của spreadsheet từ Drive"""
    service = get_sheets_service()
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    return spreadsheet["properties"]["title"]


def read_pdf(file_id: str) -> list[dict]:
    """Đọc file PDF từ Google Drive.

    Thử extract text trực tiếp bằng pypdf.
    Nếu PDF là ảnh (không có text layer) → fallback sang Google Drive OCR.
    """
    drive_service = get_drive_service()

    # supportsAllDrives=True cần thiết cho file trong Shared Drive (Team Drive)
    file_meta = drive_service.files().get(
        fileId=file_id,
        fields="name",
        supportsAllDrives=True,
    ).execute()
    filename = file_meta.get("name", file_id)

    request = drive_service.files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    reader = pypdf.PdfReader(buffer)

    chunks = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = "".join(ch for ch in text if ch >= " " or ch in "\n\r\t")
        if text.strip():
            chunks.append({
                "_sheet_name": filename,
                "_heading": f"Trang {i + 1}",
                "_content": text,
                "_row_number": i,
            })

    # PDF ảnh (scanned) → không có text layer → dùng Tesseract OCR
    if not chunks:
        print(f"  [OCR] PDF không có text layer, chuyển sang Tesseract OCR...")
        chunks = _ocr_pdf_with_tesseract(buffer, filename)

    return chunks


def _ocr_pdf_with_tesseract(pdf_buffer: io.BytesIO, filename: str) -> list[dict]:
    """OCR PDF ảnh bằng Tesseract (local, offline, miễn phí).

    Dùng PyMuPDF để render từng trang thành ảnh PIL,
    rồi pytesseract để extract text (hỗ trợ tiếng Việt).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  [OCR] Cần cài pymupdf: pip install pymupdf")
        return []

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        print("  [OCR] Cần cài pytesseract: pip install pytesseract")
        print("  [OCR] Và cài Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki")
        return []

    from config import TESSERACT_CMD
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    pdf_buffer.seek(0)
    pdf_bytes = pdf_buffer.read()

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        print(f"  [OCR] Không mở được PDF: {e}")
        return []

    total_pages = len(doc)
    print(f"  [OCR] Tổng {total_pages} trang, đang xử lý...")

    chunks = []
    for page_num in range(total_pages):
        try:
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            try:
                text = pytesseract.image_to_string(img, lang="vie+eng")
            except pytesseract.TesseractError:
                # Language pack vie chưa cài → fallback eng
                print(f"  [OCR] Trang {page_num + 1}: lang 'vie' không có, dùng 'eng'")
                text = pytesseract.image_to_string(img, lang="eng")

            # Xóa null bytes và ký tự không in được
            text = "".join(ch for ch in text if ch >= " " or ch in "\n\r\t")
            text = text.strip()

            if text:
                chunks.append({
                    "_sheet_name": filename,
                    "_heading": f"Trang {page_num + 1}",
                    "_content": text,
                    "_row_number": page_num,
                })
                print(f"  [OCR] Trang {page_num + 1}: {len(text)} ký tự")

        except pytesseract.TesseractNotFoundError:
            print("  [OCR] Tesseract chưa được cài. Hướng dẫn cài:")
            print("  [OCR]   1. Tải tại: https://github.com/UB-Mannheim/tesseract/wiki")
            print("  [OCR]   2. Chọn bản tesseract-ocr-w64-setup-*.exe")
            print("  [OCR]   3. Tick 'Vietnamese' ở phần Additional language data")
            doc.close()
            return []
        except Exception as e:
            print(f"  [OCR] Lỗi trang {page_num + 1}: {e}")
            continue

    doc.close()
    print(f"  [OCR] Hoàn thành: {len(chunks)} trang có nội dung")
    return chunks


def pdf_to_text(chunks: list[dict]) -> list[str]:
    """Convert PDF chunks thành text để index"""
    result = []
    for chunk in chunks:
        sheet = chunk.get("_sheet_name", "")
        heading = chunk.get("_heading", "")
        content = chunk.get("_content", "")
        if content.strip():
            result.append(f"=== {sheet} — {heading} ===\n{content}")
    return result


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

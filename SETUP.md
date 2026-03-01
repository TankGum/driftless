# Hướng Dẫn Cài Đặt Driftless AI Agent

> **Driftless** là AI agent nội bộ cho doanh nghiệp — trả lời câu hỏi từ knowledge base (Google Sheets/Docs/PDF), phân tích dữ liệu dự án, hỗ trợ onboarding nhân viên, soạn thảo văn bản và quản lý phản hồi ẩn danh. Chạy trên Telegram, Zalo và WebUI.

---

## Mục Lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Chuẩn bị API Keys](#2-chuẩn-bị-api-keys)
3. [Cài đặt môi trường](#3-cài-đặt-môi-trường)
4. [Cấu hình Supabase (Database)](#4-cấu-hình-supabase-database)
5. [Cấu hình Google Service Account](#5-cấu-hình-google-service-account)
6. [Tạo file `.env`](#6-tạo-file-env)
7. [Cài đặt dependencies](#7-cài-đặt-dependencies)
8. [Chạy setup script](#8-chạy-setup-script)
9. [Khởi động server](#9-khởi-động-server)
10. [Sử dụng sau khi cài đặt](#10-sử-dụng-sau-khi-cài-đặt)
11. [Tùy chọn nâng cao](#11-tùy-chọn-nâng-cao)
12. [Xử lý lỗi thường gặp](#12-xử-lý-lỗi-thường-gặp)

---

## 1. Yêu Cầu Hệ Thống

### Phần mềm bắt buộc

| Phần mềm | Phiên bản tối thiểu | Ghi chú |
|----------|---------------------|---------|
| Python | 3.10+ | Khuyến nghị 3.11 |
| pip | 23+ | Đi kèm với Python |
| Git | bất kỳ | Để clone code |

### Phần mềm tùy chọn (nếu cần đọc PDF scan/ảnh)

| Phần mềm | Link tải | Ghi chú |
|----------|----------|---------|
| Tesseract OCR | https://github.com/UB-Mannheim/tesseract/wiki | Bắt buộc nếu có PDF scan |
| Vietnamese language pack | Cài kèm Tesseract | Chọn "vie" khi cài |

> **Lưu ý Tesseract trên Windows:** Sau khi cài, thêm biến môi trường `TESSERACT_CMD` trỏ đến file `tesseract.exe`, ví dụ: `C:\Program Files\Tesseract-OCR\tesseract.exe`

---

## 2. Chuẩn Bị API Keys

Cần chuẩn bị **4 thứ** trước khi bắt đầu cài đặt:

### 2.1 Anthropic API Key (bắt buộc)

AI engine của hệ thống.

1. Truy cập https://console.anthropic.com
2. Đăng ký tài khoản (hoặc đăng nhập)
3. Vào **API Keys** → **Create Key**
4. Sao chép key bắt đầu bằng `sk-ant-...`

> **Chi phí:** Tính theo token. Hệ thống dùng `claude-sonnet-4-6` (câu trả lời chính) và `claude-haiku-4-5-20251001` (tác vụ nhẹ).

---

### 2.2 Supabase (bắt buộc)

Database lưu người dùng, tài liệu, lịch sử chat.

1. Truy cập https://supabase.com → **New Project**
2. Đặt tên project, chọn region gần nhất (Singapore hoặc Tokyo)
3. Đặt database password → **Create Project**
4. Sau khi tạo xong, vào **Project Settings → API**:
   - Sao chép **Project URL** (dạng `https://xxxx.supabase.co`)
   - Sao chép **anon public key** (dài ~200 ký tự)

---

### 2.3 Telegram Bot Token (bắt buộc nếu dùng Telegram)

1. Mở Telegram, tìm **@BotFather**
2. Gõ `/newbot` → đặt tên bot → đặt username (phải kết thúc bằng `bot`)
3. BotFather sẽ gửi token dạng `7xxxxxxxxx:AAF...`
4. Sao chép token đó

> Nếu **không dùng Telegram**, vẫn phải có token. Có thể tạo bot test tạm.

---

### 2.4 Zalo OA Token (tùy chọn)

Chỉ cần nếu muốn tích hợp Zalo.

1. Vào https://oa.zalo.me → Tạo Official Account
2. Vào **Dev Tools → API Explorer** → lấy `access_token`
3. Nếu bỏ qua, hệ thống chỉ chạy Telegram + WebUI

---

## 3. Cài Đặt Môi Trường

### Bước 1: Giải nén / clone source code

```bash
# Nếu nhận file zip:
unzip driftless.zip -d driftless
cd driftless

# Nếu nhận qua Git:
git clone <repo-url> driftless
cd driftless
```

### Bước 2: Tạo Python virtual environment

```bash
# Tạo venv
python -m venv .venv

# Kích hoạt venv
# Linux / macOS:
source .venv/bin/activate

# Windows (Command Prompt):
.venv\Scripts\activate.bat

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

> Sau khi kích hoạt, terminal sẽ hiển thị `(.venv)` ở đầu dòng.

---

## 4. Cấu Hình Supabase (Database)

### Bước 1: Chạy migration script

1. Mở Supabase Dashboard → project của bạn
2. Vào **SQL Editor** (icon database bên trái)
3. Nhấn **New query**
4. Mở file `scripts/migrate.sql` (trong thư mục source code)
5. Copy toàn bộ nội dung → Paste vào SQL Editor
6. Nhấn **Run** (hoặc Ctrl+Enter)

Kết quả thành công sẽ hiển thị các bảng: `companies`, `users`, `data_sources`, `documents`, `document_chunks`, `chat_messages`, `chat_sessions`.

### Bước 2: Kích hoạt extension pgvector

Nếu gặp lỗi `extension "vector" does not exist`:

1. Vào **Database → Extensions**
2. Tìm `vector` → Enable

Sau đó chạy lại migration.

### Bước 3: Reload schema cache

Chạy lệnh này trong SQL Editor sau khi migration xong:

```sql
NOTIFY pgrst, 'reload schema';
```

---

## 5. Cấu Hình Google Service Account

Dùng để đọc Google Sheets, Google Docs và Google Drive.

### Bước 1: Tạo Service Account

1. Vào https://console.cloud.google.com
2. Tạo project mới (hoặc chọn project có sẵn)
3. Vào **APIs & Services → Enable APIs and Services**
4. Enable các APIs sau:
   - **Google Sheets API**
   - **Google Docs API**
   - **Google Drive API**
5. Vào **IAM & Admin → Service Accounts → Create Service Account**
6. Đặt tên (ví dụ: `driftless-agent`) → **Create and Continue**
7. Bỏ qua phần cấp quyền → **Done**

### Bước 2: Tạo và tải credentials

1. Click vào service account vừa tạo
2. Vào tab **Keys → Add Key → Create new key**
3. Chọn **JSON** → **Create**
4. File `credentials.json` sẽ tự tải về
5. Copy file này vào thư mục gốc của dự án (cùng cấp với `main.py`)

### Bước 3: Share Google Sheets/Docs với Service Account

Khi thêm tài liệu mới, cần share Google Sheet/Doc với email của service account (dạng `xxx@xxx.iam.gserviceaccount.com`). Quyền **Viewer** là đủ.

> Email service account nằm trong file `credentials.json` ở trường `client_email`.

---

## 6. Tạo File `.env`

Tạo file `.env` trong thư mục gốc dự án (cùng cấp với `main.py`):

```bash
# Bắt buộc
TELEGRAM_TOKEN=7xxxxxxxxx:AAF...
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs...
CLAUDE_API_KEY=sk-ant-api03-...
GOOGLE_CREDENTIALS_PATH=credentials.json

# Tùy chọn — Zalo (bỏ qua nếu không dùng)
ZALO_BOT_TOKEN=your_zalo_token_here

# Tùy chọn — URL public (cần nếu dùng Telegram webhook thay vì polling)
# BASE_URL=https://your-domain.com

# Tùy chọn — Mật khẩu WebUI (mặc định: driftless2024)
CHAINLIT_ADMIN_PASSWORD=your_secure_password

# Tùy chọn — Tesseract (Windows)
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Tùy chọn — LangSmith monitoring
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=ls__...
```

> **Lưu ý bảo mật:** Không commit file `.env` lên Git. File `.gitignore` đã bao gồm `.env`.

---

## 7. Cài Đặt Dependencies

Đảm bảo venv đang được kích hoạt (`(.venv)` hiển thị ở terminal):

```bash
pip install -r requirements.txt
```

Quá trình này mất khoảng **5-15 phút** tùy tốc độ mạng vì cần tải:
- Các model AI embedding (`intfloat/multilingual-e5-large` ~1.1GB) — tải tự động lần đầu chạy
- Các model reranker (`ms-marco-MiniLM-L-6-v2`) — tải tự động lần đầu chạy
- Các thư viện Python

---

## 8. Chạy Setup Script

Script này tạo tài khoản admin và công ty trong database:

```bash
python scripts/setup.py
```

Script sẽ hỏi lần lượt:

```
==================================================
  DRIFTLESS — Setup Script
==================================================

✅ Env vars OK
✅ Google credentials OK
✅ Supabase connection OK
✅ Database tables OK

Công ty dùng platform nào?
  [1] Telegram
  [2] Zalo
  [3] Cả hai (Telegram + Zalo)
Chọn (1/2/3): 1

  Tên công ty: Công ty ABC
  Tên admin: admin_abc
  Mật khẩu WebUI của admin (≥6 ký tự): ••••••••
  Telegram ID của admin (lấy từ @userinfobot): 123456789
```

### Cách lấy Telegram ID

1. Mở Telegram, tìm **@userinfobot**
2. Gõ `/start`
3. Bot sẽ trả về ID dạng số (ví dụ: `123456789`)

### Kết quả thành công

```
✅ Tạo company 'Công ty ABC' thành công
   Company ID: cong-ty-abc
✅ Đã ghi DEFAULT_COMPANY_ID=cong-ty-abc vào .env

==================================================
  ✅ Setup hoàn thành!
==================================================

Bước tiếp theo:
1. Chạy: python main.py
2. Mở Telegram, tìm bot và gõ /start
3. Dùng /adddoc để thêm tài liệu
4. Dùng /invite để tạo invite code cho team
```

---

## 9. Khởi Động Server

```bash
python main.py
```

Server sẽ khởi động:
- **WebUI:** http://localhost:8000
- **Telegram bot:** polling tự động
- **Zalo bot:** polling tự động (nếu có token)
- **API REST:** http://localhost:8000/api

### Kiểm tra hoạt động

1. Mở http://localhost:8000 trên trình duyệt
2. Đăng nhập bằng username/password đã tạo ở bước 8
3. Mở Telegram → tìm bot → gõ `/start`
4. Bot sẽ chào và hiển thị menu lệnh

### Chạy ở chế độ development (auto-reload)

```bash
uvicorn main:app --reload --port 8000
```

---

## 10. Sử Dụng Sau Khi Cài Đặt

### 10.1 Thêm tài liệu vào knowledge base

**Qua Telegram:**
```
/adddoc https://docs.google.com/spreadsheets/d/...
/adddoc https://docs.google.com/document/d/...
```

**Qua WebUI:** Nhấn nút upload file (góc phải) để tải PDF, DOCX, TXT.

> Nhớ share Google Sheet/Doc với email service account trước!

### 10.2 Mời thành viên vào team

**Qua Telegram:**
```
/invite
```
Bot sẽ tạo invite code. Thành viên mới gõ:
```
/join <invite_code>
```

### 10.3 Các lệnh Telegram chính

| Lệnh | Quyền | Mô tả |
|------|-------|-------|
| `/start` | Tất cả | Bắt đầu / giới thiệu |
| `/help` | Tất cả | Danh sách lệnh |
| `/adddoc <url>` | Admin | Thêm tài liệu |
| `/listdocs` | PM+ | Xem danh sách tài liệu |
| `/sync` | Admin | Đồng bộ lại tài liệu |
| `/invite` | Admin | Tạo invite code |
| `/join <code>` | Tất cả | Tham gia công ty |
| `/setrole` | Admin | Phân quyền thành viên |
| `/summary` | PM+ | Tóm tắt dự án |
| `/risk` | PM+ | Cảnh báo rủi ro |
| `/feedback` | Tất cả | Gửi phản hồi ẩn danh |
| `/viewfeedback` | Admin | Xem phản hồi ẩn danh |

### 10.4 Hỏi đáp tự do

Sau khi thêm tài liệu và đồng bộ, thành viên chỉ cần nhắn tin bình thường để hỏi:
- "Chính sách nghỉ phép của công ty là gì?"
- "Tiến độ dự án X tháng này thế nào?"
- "Dự báo KPI quý tới có đạt không?"

---

## 11. Tùy Chọn Nâng Cao

### 11.1 Chạy trên server (production)

Khuyến nghị dùng `systemd` hoặc `supervisor` để chạy nền:

```bash
# Ví dụ với nohup
nohup python main.py > logs/app.log 2>&1 &
```

Hoặc tạo file `driftless.service` cho systemd:

```ini
[Unit]
Description=Driftless AI Agent
After=network.target

[Service]
WorkingDirectory=/path/to/driftless
ExecStart=/path/to/driftless/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 11.2 Đồng bộ tài liệu thủ công

```bash
python scripts/sync_sheets.py
```

> Hệ thống tự đồng bộ mỗi giờ. Lệnh này để buộc đồng bộ ngay lập tức.

### 11.3 Quản lý người dùng qua script

```bash
python scripts/manage_users.py
```

### 11.4 Theo dõi với LangSmith

Thêm vào `.env`:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__xxxx
```

Sau đó xem trace tại https://smith.langchain.com.

---

## 12. Xử Lý Lỗi Thường Gặp

### Lỗi: `❌ Thiếu các env vars`

**Nguyên nhân:** File `.env` chưa đầy đủ hoặc chưa tồn tại.

**Giải quyết:** Kiểm tra lại file `.env`, đảm bảo có đủ 5 biến bắt buộc (xem mục 6).

---

### Lỗi: `❌ Supabase connection failed`

**Nguyên nhân:** `SUPABASE_URL` hoặc `SUPABASE_KEY` sai.

**Giải quyết:**
1. Vào Supabase Dashboard → Project Settings → API
2. Copy lại đúng URL và anon key
3. Đảm bảo không có khoảng trắng thừa trong `.env`

---

### Lỗi: `❌ Các bảng chưa được tạo`

**Nguyên nhân:** Chưa chạy migration SQL hoặc chạy bị lỗi.

**Giải quyết:** Chạy lại toàn bộ nội dung `scripts/migrate.sql` trong Supabase SQL Editor.

---

### Lỗi: `extension "vector" does not exist`

**Nguyên nhân:** Extension pgvector chưa được bật.

**Giải quyết:**
1. Vào Supabase Dashboard → Database → Extensions
2. Tìm `vector` → Enable
3. Chạy lại migration

---

### Lỗi: `Google API error: 403 Forbidden`

**Nguyên nhân:** Google Sheet/Doc chưa được share với service account.

**Giải quyết:**
1. Mở file `credentials.json`, tìm `client_email`
2. Share Google Sheet/Doc đó với email này (quyền Viewer)

---

### Lỗi: Bot Telegram không phản hồi

**Nguyên nhân:** `TELEGRAM_TOKEN` sai hoặc bot chưa được tìm đúng.

**Giải quyết:**
1. Kiểm tra token trong `.env`
2. Đảm bảo tìm đúng username bot (đuôi `bot`)
3. Xem log terminal khi chạy `python main.py`

---

### Model AI tải chậm lần đầu

**Nguyên nhân:** Lần đầu chạy, hệ thống tải model embedding (~1.1GB) và reranker về máy.

**Giải quyết:** Chờ tải xong (5-20 phút tùy tốc độ mạng). Các lần sau khởi động nhanh bình thường.

---

### Lỗi PDF scan không đọc được

**Nguyên nhân:** Tesseract chưa được cài hoặc chưa có gói ngôn ngữ tiếng Việt.

**Giải quyết:**
1. Cài Tesseract (xem mục 1)
2. Cài thêm language pack `vie`
3. Trên Windows, thêm `TESSERACT_CMD` vào `.env`

---

## Hỗ Trợ

Nếu gặp vấn đề không có trong danh sách trên, vui lòng cung cấp:
1. Nội dung lỗi (copy từ terminal)
2. Hệ điều hành và phiên bản Python
3. Bước đang thực hiện khi gặp lỗi

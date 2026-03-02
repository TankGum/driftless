# Hướng Dẫn Sử Dụng Driftless AI Agent

> Tài liệu này dành cho **toàn bộ nhân viên** — từ Admin đến thành viên thông thường — sau khi hệ thống đã được cài đặt và khởi động.

---

## Mục Lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Vai trò (Role) trong hệ thống](#2-vai-trò-role-trong-hệ-thống)
3. [Bắt đầu sử dụng — lần đầu đăng ký](#3-bắt-đầu-sử-dụng--lần-đầu-đăng-ký)
4. [Hỏi đáp tự do](#4-hỏi-đáp-tự-do)
5. [Quản lý tài liệu (Admin)](#5-quản-lý-tài-liệu-admin)
6. [Quản lý thành viên](#6-quản-lý-thành-viên)
7. [Analytics & Dự báo (PM/Admin)](#7-analytics--dự-báo-pmadmin)
8. [Soạn thảo văn bản](#8-soạn-thảo-văn-bản)
9. [Phản hồi ẩn danh](#9-phản-hồi-ẩn-danh)
10. [WebUI — Giao diện trình duyệt](#10-webui--giao-diện-trình-duyệt)
11. [Bảng tổng hợp lệnh](#11-bảng-tổng-hợp-lệnh)

---

## 1. Tổng Quan Hệ Thống

Driftless hoạt động trên **3 nền tảng** đồng thời:

| Nền tảng | Truy cập | Phù hợp |
|----------|----------|---------|
| **Telegram** | Tìm bot trên Telegram | Chat nhanh, nhóm |
| **Zalo** | Tìm Official Account trên Zalo | Nhân viên dùng Zalo |
| **WebUI** | Trình duyệt: `http://server:8000` | Giao diện đầy đủ, lịch sử chat |

Dữ liệu người dùng được **chia sẻ** giữa các nền tảng — một tài khoản admin có thể quản lý qua bất kỳ nền tảng nào.

---

## 2. Vai Trò (Role) Trong Hệ Thống

Hệ thống có **3 vai trò** với quyền hạn khác nhau:

| Role | Ký hiệu | Quyền |
|------|---------|-------|
| **Admin** | 🛡️ | Toàn quyền: thêm/xóa tài liệu, sync, quản lý thành viên, xem phản hồi ẩn danh |
| **PM** | 🎯 | Xem tài liệu, analytics, dự báo, upload file |
| **Member** | 👤 | Hỏi đáp kiến thức, soạn thảo, gửi phản hồi ẩn danh |

> Mặc định khi đăng ký lần đầu, tất cả thành viên đều là **Member**. Chỉ Admin mới nâng quyền được.

---

## 3. Bắt Đầu Sử Dụng — Lần Đầu Đăng Ký

### Trên Telegram

1. Mở Telegram → Tìm kiếm tên bot (do Admin cung cấp)
2. Nhấn **Start** hoặc gõ `/start`
3. Bot sẽ chào và tự động ghi nhận tài khoản của bạn

```
Bot: Xin chào Nguyễn Văn A!
Tôi là Driftless — AI Agent của công ty bạn.
Hỏi tôi bất cứ điều gì về quy trình, tài liệu, hay dự án.

Gõ /help để xem các lệnh có sẵn.
```

### Trên Zalo

1. Mở Zalo → Tìm Official Account của công ty
2. Gửi tin nhắn `start` hoặc `/start`
3. Bot sẽ chào và đăng ký tài khoản

### Nếu có nhiều công ty (multi-tenant)

Trường hợp hệ thống phục vụ nhiều công ty, Admin sẽ cung cấp **invite code**. Sau khi gõ `/start`, dùng lệnh:

```
/join ABC12345
```

Thay `ABC12345` bằng invite code do Admin cung cấp.

---

## 4. Hỏi Đáp Tự Do

Đây là tính năng **cốt lõi** — chỉ cần nhắn tin bình thường, bot tự hiểu và trả lời.

### Hỏi về kiến thức / quy trình

Nhắn thẳng câu hỏi, không cần lệnh:

```
Chính sách nghỉ phép của công ty là gì?
Quy trình xin tăng ca như thế nào?
Chế độ bảo hiểm nhân viên có bao gồm gì?
Onboarding nhân viên mới cần làm những bước gì?
```

### Hỏi về dữ liệu dự án (Analytics)

```
KPI tháng này của team A đạt bao nhiêu %?
Tiến độ dự án X hiện tại ra sao?
Hiệu suất team nào đang cao nhất?
```

### Hỏi dự báo (Forecast)

```
Dự án Y có nguy cơ trễ deadline không?
KPI quý tới có đạt được không?
Team nào đang bị quá tải?
```

### Trong nhóm Telegram

Trong nhóm (group chat), cần **tag bot** hoặc **reply tin nhắn của bot** để kích hoạt:

```
@TenBot chính sách nghỉ phép là gì?
```

Hoặc reply vào tin nhắn bot đã gửi trước đó.

> Trong chat riêng (private), nhắn thẳng không cần tag.

---

## 5. Quản Lý Tài Liệu (Admin)

### 5.1 Thêm tài liệu từ Google Sheets / Docs

**Bước 1:** Share Google Sheet/Doc với email service account (Admin đã có sẵn email này)
- Mở Google Sheet/Doc → **Share** → paste email service account → quyền **Viewer**

**Bước 2:** Thêm vào hệ thống

```
/adddoc https://docs.google.com/spreadsheets/d/1ABC.../edit
/adddoc https://docs.google.com/document/d/1XYZ.../edit
```

Bot sẽ xác nhận:
```
✅ Đã thêm và index: "Chính sách nhân sự 2024"
   Tổng chunks: 47
```

**Loại tài liệu được hỗ trợ:**
- Google Sheets (mọi tab)
- Google Docs
- Google Drive PDF

### 5.2 Upload file trực tiếp (WebUI hoặc API)

Qua **WebUI** (`http://server:8000`):
1. Đăng nhập → Nhấn icon upload góc phải giao diện chat
2. Chọn file PDF, DOCX hoặc TXT
3. Hệ thống tự index và thông báo hoàn thành

> PDF dạng scan/ảnh cũng được hỗ trợ (dùng OCR tiếng Việt).

### 5.3 Xem danh sách tài liệu

```
/listdocs
```

Kết quả:
```
📚 Tài liệu đang active (3):

1. Chính sách nhân sự 2024
   🔗 Google Docs | ✅ Synced: 2024-01-15 08:30

2. KPI Q1 2024
   🔗 Google Sheets | ✅ Synced: 2024-01-15 08:30

3. Onboarding Guide
   📄 File upload | ✅ Synced: 2024-01-14 14:22
```

### 5.4 Xóa tài liệu

```
/removedoc https://docs.google.com/spreadsheets/d/1ABC.../edit
```

### 5.5 Đồng bộ lại tài liệu

Hệ thống **tự động đồng bộ mỗi giờ**. Để đồng bộ ngay lập tức khi có thay đổi:

```
/resyncdocs
```

### 5.6 Xem trạng thái đồng bộ

```
/syncstatus
```

Kết quả:
```
📊 Trạng thái sync:

Chính sách nhân sự 2024
   ✅ 2024-01-15 08:30

KPI Q1 2024
   ⚠️ Chưa sync

Auto-sync mỗi giờ 1 lần
```

---

## 6. Quản Lý Thành Viên

### 6.1 Tạo invite code (Admin)

```
/invite
```

Bot trả về một mã code (8 ký tự, ví dụ: `XK92PLMN`). Gửi code này cho nhân viên mới.

### 6.2 Thành viên mới tham gia

Nhân viên nhận được code → gõ:

```
/join XK92PLMN
```

Bot xác nhận:
```
✅ Đã tham gia Công ty ABC! Gõ /help để bắt đầu.
```

### 6.3 Xem role của mình

```
/myrole
```

Kết quả:
```
🎯 Role của bạn: PM
```

### 6.4 Phân quyền thành viên (Admin)

**Trên Telegram:**
```
/setrole @username pm
/setrole @username admin
/setrole @username member
```

**Trên Zalo:**
```
/setrole username pm
```

> Nhân viên cần gõ `/start` trước thì mới được phân quyền. Nếu bot báo "không tìm thấy", hãy nhờ nhân viên đó gõ `/start` trước.

**Các role hợp lệ:** `admin`, `pm`, `member`

---

## 7. Analytics & Dự Báo (PM/Admin)

Bot tự động nhận biết câu hỏi analytics và forecast qua từ khóa. Không cần lệnh đặc biệt — chỉ cần hỏi bằng ngôn ngữ tự nhiên.

### Analytics — Phân tích dữ liệu thực tế

Bot đọc trực tiếp từ Google Sheets (các tab tên "Project Progress", "KPI Tracking", "Team Performance"):

```
KPI tháng này của team nào cao nhất?
Tiến độ các dự án đang chạy thế nào?
Hiệu suất tổng thể tháng 1 là bao nhiêu?
```

### Forecast — Dự báo rủi ro

```
Dự án nào có nguy cơ trễ deadline?
Team nào đang bị quá tải công việc?
Dự báo KPI quý tới có đạt không?
Cảnh báo rủi ro hiện tại là gì?
```

> **Lưu ý:** Analytics và Forecast chỉ chạy được khi đã có Google Sheets với dữ liệu dự án được thêm vào hệ thống qua `/adddoc`.

---

## 8. Soạn Thảo Văn Bản

Bot hỗ trợ soạn thảo các loại văn bản nội bộ. Dùng ngôn ngữ tự nhiên:

```
Viết email thông báo nghỉ lễ 30/4 cho toàn công ty
Soạn thư mời họp ban giám đốc ngày 20/2
Giúp tôi viết quy trình onboarding nhân viên mới IT
Draft báo cáo tóm tắt tiến độ dự án tháng 1
```

Bot sẽ tạo bản nháp hoàn chỉnh, có thể chỉnh sửa thêm.

---

## 9. Phản Hồi Ẩn Danh

### Gửi phản hồi (tất cả thành viên)

```
/feedback Tôi thấy quy trình báo cáo hàng tuần khá rườm rà, nên xem xét lại.
```

Bot xác nhận đã nhận, danh tính người gửi **không được lưu**.

### Xem phản hồi (Admin)

```
/viewfeedback
```

Bot liệt kê tất cả phản hồi đã nhận, không hiển thị ai gửi.

---

## 10. WebUI — Giao Diện Trình Duyệt

Truy cập `http://[địa-chỉ-server]:8000` trên trình duyệt.

### Đăng nhập

- **Username:** tên đăng nhập do Admin tạo
- **Password:** mật khẩu đã đặt khi setup (hoặc được Admin cấp)

> Admin cấp tài khoản WebUI cho thành viên qua script `scripts/manage_users.py` hoặc trực tiếp trong Supabase.

### Tính năng WebUI

**Chat có lịch sử:**
- Lịch sử hội thoại được lưu theo phiên (session)
- Xem lại các cuộc hội thoại cũ ở sidebar trái
- Ghim (pin) các phiên quan trọng

**Upload file:**
- Nhấn icon upload trong giao diện chat
- Hỗ trợ PDF, DOCX, TXT
- Hệ thống tự phát hiện file trùng nội dung và hỏi có muốn thay thế không

**Streaming response:**
- Câu trả lời được hiển thị từng từ theo thời gian thực (không cần chờ toàn bộ)

---

## 11. Bảng Tổng Hợp Lệnh

### Telegram

| Lệnh | Quyền | Mô tả |
|------|-------|-------|
| `/start` | Tất cả | Đăng ký / chào hỏi |
| `/help` | Tất cả | Xem danh sách lệnh |
| `/myrole` | Tất cả | Xem role hiện tại |
| `/join [code]` | Tất cả | Tham gia công ty bằng invite code |
| `/feedback [nội dung]` | Tất cả | Gửi phản hồi ẩn danh |
| `/listdocs` | PM / Admin | Xem danh sách tài liệu |
| `/syncstatus` | PM / Admin | Xem trạng thái đồng bộ |
| `/adddoc [url]` | Admin | Thêm Google Sheet/Doc |
| `/removedoc [url]` | Admin | Xóa tài liệu |
| `/resyncdocs` | Admin | Đồng bộ lại toàn bộ tài liệu |
| `/invite` | Admin | Tạo invite code cho thành viên |
| `/setrole @user [role]` | Admin | Phân quyền thành viên |
| `/viewfeedback` | Admin | Xem phản hồi ẩn danh |

### Zalo

Tương tự Telegram nhưng **không có Markdown** và không cần `@username` khi setrole:

| Lệnh | Quyền | Mô tả |
|------|-------|-------|
| `/start` | Tất cả | Đăng ký / chào hỏi |
| `/help` | Tất cả | Xem danh sách lệnh |
| `/join [code]` | Tất cả | Tham gia công ty |
| `/myrole` | Tất cả | Xem role |
| `/listdocs` | PM / Admin | Danh sách tài liệu |
| `/syncstatus` | PM / Admin | Trạng thái sync |
| `/adddoc [url]` | Admin | Thêm tài liệu |
| `/removedoc [url]` | Admin | Xóa tài liệu |
| `/resyncdocs` | Admin | Sync lại tài liệu |
| `/setrole [username] [role]` | Admin | Phân quyền |

---

## Câu Hỏi Thường Gặp

**Q: Bot trả lời "Tôi không có thông tin về vấn đề này" — tại sao?**

A: Tài liệu chứa thông tin đó chưa được thêm vào hệ thống, hoặc nội dung tài liệu chưa có câu trả lời phù hợp. Liên hệ Admin để bổ sung tài liệu.

---

**Q: Bot trả lời sai hoặc thiếu chính xác?**

A: Chất lượng câu trả lời phụ thuộc vào nội dung tài liệu. Hãy:
1. Kiểm tra tài liệu gốc có đúng thông tin không
2. Thử hỏi lại với câu cụ thể hơn
3. Báo cáo cho Admin để cập nhật tài liệu

---

**Q: Tôi muốn đổi mật khẩu WebUI?**

A: Liên hệ Admin. Admin có thể cập nhật trong Supabase Dashboard → Table `users` → cột `password_hash`.

---

**Q: Tài liệu vừa cập nhật nhưng bot chưa biết?**

A: Hệ thống tự đồng bộ mỗi giờ. Nếu cần ngay, Admin gõ `/resyncdocs` để đồng bộ thủ công.

---

**Q: Làm sao biết email service account để share Google Sheet?**

A: Hỏi Admin. Email nằm trong file `credentials.json` ở trường `client_email`, dạng `xxx@xxx-project.iam.gserviceaccount.com`.

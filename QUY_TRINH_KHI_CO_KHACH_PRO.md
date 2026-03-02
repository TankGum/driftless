---
 Quy trình thực tế khi có khách Pro

 Cần chuẩn bị trước (1 lần, dùng mãi)

 ┌────────────────────────┬───────────────────────────────┬───────────────────────────────────┐
 │         Thứ gì         │             Ở đâu             │              Ghi chú              │
 ├────────────────────────┼───────────────────────────────┼───────────────────────────────────┤
 │ Supabase project       │ Cloud (driftless.supabase.co) │ Dùng chung cho tất cả tenant      │
 ├────────────────────────┼───────────────────────────────┼───────────────────────────────────┤
 │ Claude API key         │ Anthropic                     │ Dùng chung (tính tiền theo usage) │
 ├────────────────────────┼───────────────────────────────┼───────────────────────────────────┤
 │ Google service account │ Google Cloud                  │ Dùng chung — credentials.json     │
 ├────────────────────────┼───────────────────────────────┼───────────────────────────────────┤
 │ Domain chính           │ DNS                           │ Ví dụ driftless.vn                │
 └────────────────────────┴───────────────────────────────┴───────────────────────────────────┘

 ---
 Bước 1 — Nhận VPS của khách

 Khách cấp cho mình:
 - IP VPS
 - SSH key hoặc password root/sudo

 VPS yêu cầu tối thiểu:
 - Ubuntu 22.04+ hoặc Debian 12
 - RAM ≥ 4 GB (ML models cần ~2 GB khi load)
 - Docker + Docker Compose đã cài (hoặc mình cài)

 ---
 Bước 2 — Setup VPS lần đầu

 SSH vào VPS, chạy:

 # Cài Docker nếu chưa có
 curl -fsSL https://get.docker.com | sh
 usermod -aG docker $USER

 # Cài nginx
 apt install -y nginx

 # Clone dự án
 git clone https://github.com/your-org/driftless.git /opt/driftless
 cd /opt/driftless/Driftless

 # Copy credentials.json (Google service account — dùng chung)
 scp credentials.json root@VPS_IP:/opt/driftless/Driftless/credentials.json

 ---
 Bước 3 — Tạo file .env gốc (secrets dùng chung)

 Tạo /opt/driftless/Driftless/.env:

 SUPABASE_URL=https://xxxx.supabase.co
 SUPABASE_KEY=eyJhbGci...
 CLAUDE_API_KEY=sk-ant-...
 GOOGLE_CREDENTIALS_PATH=/app/credentials.json

 ---
 Bước 4 — Build Docker image (1 lần, ~5-10 phút)

 cd /opt/driftless/Driftless
 docker build -t driftless:latest .

 Image này dùng chung cho tất cả khách trên VPS đó. Chỉ cần rebuild khi update code.

 ---
 Bước 5 — Provision tenant mới bằng script

 Chạy provision.py một lệnh duy nhất:

 python scripts/provision.py \
   --company "Tên Công Ty Khách" \
   --subdomain ten-cong-ty \
   --token 1234567890:ABCxxx \        # Telegram bot token của khách
   --admin-username admin@email.com \
   --admin-password matkhau_manh \
   --base-domain driftless.vn

 Script này tự động làm:
 1. Tạo company_id duy nhất trong Supabase
 2. Tạo user admin trong Supabase
 3. Tìm port trống (8100, 8101, ...)
 4. Tạo deployments/ten-cong-ty/docker-compose.yml và .env
 5. Chạy docker compose up -d → container lên
 6. Viết nginx config /etc/nginx/conf.d/ten-cong-ty.conf
 7. Reload nginx

 Kết quả: http://ten-cong-ty.driftless.vn → WebUI Chainlit

 ---
 Bước 6 — Trỏ DNS (nếu domain khách muốn riêng)

 Trường hợp A — Dùng subdomain của mình (đơn giản):
 - Chỉ cần thêm A record *.driftless.vn → IP VPS
 - Xong ngay, không cần làm gì thêm

 Trường hợp B — Khách muốn domain riêng (vd: chat.cong-ty-khach.vn):
 - Khách trỏ A record chat.cong-ty-khach.vn → IP VPS
 - Mình thêm server_name chat.cong-ty-khach.vn; vào nginx config

 ---
 Bước 7 — Cấu hình bot Telegram và Zalo

 Telegram:
 - Khách tự tạo bot qua @BotFather → lấy token
 - Paste token vào --token khi chạy provision.py
 - Bot tự start polling khi container up — không cần webhook, không cần domain cho bot

 Zalo:
 - Thêm ZALO_BOT_TOKEN=xxx vào .env của tenant
 - Restart container: docker compose restart
 - Zalo cần webhook public URL — cần SSL (bước 8)

 ---
 Bước 8 — SSL (HTTPS) nếu cần

 apt install certbot python3-certbot-nginx
 certbot --nginx -d ten-cong-ty.driftless.vn

 Certbot tự cập nhật nginx config, tự renew.

 ---
 Tóm tắt: Mỗi khách Pro mới tốn bao lâu?

 ┌───────────────────────────┬─────────────────────────────────┐
 │           Bước            │            Thời gian            │
 ├───────────────────────────┼─────────────────────────────────┤
 │ SSH + clone + build image │ ~10 phút (lần đầu trên VPS mới) │
 ├───────────────────────────┼─────────────────────────────────┤
 │ Chạy provision.py         │ < 1 phút                        │
 ├───────────────────────────┼─────────────────────────────────┤
 │ DNS propagation           │ 1-10 phút                       │
 ├───────────────────────────┼─────────────────────────────────┤
 │ SSL cert                  │ < 2 phút                        │
 ├───────────────────────────┼─────────────────────────────────┤
 │ Tổng (VPS đã setup)       │ ~5 phút/khách                   │
 └───────────────────────────┴─────────────────────────────────┘

 ---
 Kiến trúc cuối cùng (mỗi khách Pro)

 [Khách hàng]
     ↓
 chat.cong-ty-khach.vn  (domain riêng hoặc subdomain.driftless.vn)
     ↓
 Nginx (VPS)
     ↓
 Docker container: driftless-ten-cong-ty (port 810X:8000)
     ├── Chainlit WebUI  → chat qua browser
     ├── Telegram bot    → polling, nhận tin nhắn từ Telegram
     └── Zalo bot        → polling, nhận tin nhắn từ Zalo
     ↓
 Supabase (cloud, dùng chung — dữ liệu isolated theo company_id)

 ---
 Điểm cần cải thiện (optional, sau này)

 ┌─────────────────────────────────────────────┬───────────┬─────────────────────────────────────┐
 │                   Vấn đề                    │  Mức độ   │              Giải pháp              │
 ├─────────────────────────────────────────────┼───────────┼─────────────────────────────────────┤
 │ provision.py hardcode path credentials      │ Thấp      │ Thêm --credentials arg              │
 ├─────────────────────────────────────────────┼───────────┼─────────────────────────────────────┤
 │ Không có script "teardown" tenant           │ Trung     │ Thêm deprovision.py                 │
 │                                             │ bình      │                                     │
 ├─────────────────────────────────────────────┼───────────┼─────────────────────────────────────┤
 │ Mỗi VPS mới phải setup thủ công             │ Cao       │ Ansible playbook hoặc bash setup    │
 │                                             │           │ script                              │
 ├─────────────────────────────────────────────┼───────────┼─────────────────────────────────────┤
 │ Multi-VPS tracking (nhiều khách Pro = nhiều │ Cao       │ Portal quản lý danh sách VPS + SSH  │
 │  VPS)                                       │           │ key                                 │
 └─────────────────────────────────────────────┴───────────┴─────────────────────────────────────┘
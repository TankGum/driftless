"""Self-service company registration — GET /register form + POST /api/provision/register."""
import re
import secrets
import unicodedata

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter()

# ── HTML registration form ─────────────────────────────────────────────────────

_REGISTER_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Đăng ký dùng thử Driftless</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f5f5f5; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; padding: 20px; }
    .card { background: #fff; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,.08);
            padding: 40px; width: 100%; max-width: 480px; }
    h1 { font-size: 1.6rem; color: #1a1a2e; margin-bottom: 6px; }
    .subtitle { color: #666; font-size: .92rem; margin-bottom: 28px; }
    label { display: block; font-size: .85rem; font-weight: 600; color: #444;
            margin-bottom: 4px; margin-top: 16px; }
    input { width: 100%; padding: 10px 14px; border: 1.5px solid #ddd;
            border-radius: 8px; font-size: .95rem; transition: border-color .2s; }
    input:focus { outline: none; border-color: #6c5ce7; }
    .hint { font-size: .78rem; color: #888; margin-top: 4px; }
    button { width: 100%; margin-top: 28px; padding: 13px;
             background: #6c5ce7; color: #fff; border: none; border-radius: 8px;
             font-size: 1rem; font-weight: 600; cursor: pointer; transition: background .2s; }
    button:hover { background: #5a4bd1; }
    button:disabled { background: #aaa; cursor: not-allowed; }
    #status { margin-top: 16px; padding: 12px; border-radius: 8px;
              font-size: .9rem; display: none; }
    .success { background: #d4edda; color: #155724; }
    .error   { background: #f8d7da; color: #721c24; }
    .trial-badge { background: #ffeaa7; color: #856404; padding: 10px 14px;
                   border-radius: 8px; font-size: .85rem; margin-bottom: 20px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🚀 Dùng thử Driftless</h1>
    <p class="subtitle">AI Agent nội bộ cho doanh nghiệp của bạn</p>

    <div class="trial-badge">
      ⏱️ <strong>Dùng thử miễn phí:</strong> 7 ngày hoặc 50 câu hỏi
    </div>

    <form id="regForm">
      <label for="company_name">Tên công ty *</label>
      <input id="company_name" name="company_name" type="text"
             placeholder="Công ty TNHH ABC" required />

      <label for="admin_username">Tên đăng nhập admin *</label>
      <input id="admin_username" name="admin_username" type="text"
             placeholder="admin" required />

      <label for="admin_password">Mật khẩu (tối thiểu 8 ký tự) *</label>
      <input id="admin_password" name="admin_password" type="password"
             placeholder="••••••••" minlength="8" required />

      <label for="admin_telegram_id">Telegram ID của admin</label>
      <input id="admin_telegram_id" name="admin_telegram_id" type="number"
             placeholder="123456789 (tuỳ chọn)" />
      <p class="hint">
        Lấy ID: nhắn tin cho <a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>
      </p>

      <label for="telegram_token">Telegram Bot Token *</label>
      <input id="telegram_token" name="telegram_token" type="text"
             placeholder="123456:ABCdef..." required />
      <p class="hint">
        Tạo bot mới: nhắn tin cho <a href="https://t.me/BotFather" target="_blank">@BotFather</a>
        → /newbot → copy token
      </p>

      <button type="submit" id="submitBtn">Đăng ký dùng thử</button>
    </form>

    <div id="status"></div>
  </div>

  <script>
    document.getElementById("regForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = document.getElementById("submitBtn");
      const statusEl = document.getElementById("status");
      btn.disabled = true;
      btn.textContent = "Đang xử lý...";
      statusEl.style.display = "none";

      const payload = {
        company_name:      document.getElementById("company_name").value.trim(),
        admin_username:    document.getElementById("admin_username").value.trim(),
        admin_password:    document.getElementById("admin_password").value,
        admin_telegram_id: parseInt(document.getElementById("admin_telegram_id").value) || 0,
        telegram_token:    document.getElementById("telegram_token").value.trim(),
      };

      try {
        const res = await fetch("/api/provision/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        statusEl.style.display = "block";
        if (res.ok) {
          statusEl.className = "success";
          statusEl.innerHTML = `
            ✅ <strong>Đăng ký thành công!</strong><br><br>
            🌐 WebUI của bạn: <a href="http://${data.subdomain}.driftless.vn">${data.subdomain}.driftless.vn</a><br>
            ⏳ Hệ thống đang khởi động (1–2 phút)…<br><br>
            Đội ngũ Driftless sẽ liên hệ bạn sớm.
          `;
          btn.textContent = "Đã đăng ký";
        } else {
          statusEl.className = "error";
          statusEl.textContent = "❌ " + (data.detail || "Đã có lỗi xảy ra.");
          btn.disabled = false;
          btn.textContent = "Thử lại";
        }
      } catch (err) {
        statusEl.style.display = "block";
        statusEl.className = "error";
        statusEl.textContent = "❌ Lỗi kết nối. Vui lòng thử lại.";
        btn.disabled = false;
        btn.textContent = "Thử lại";
      }
    });
  </script>
</body>
</html>"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


async def _validate_telegram_token(token: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url)
        return resp.status_code == 200 and resp.json().get("ok", False)
    except Exception:
        return False


def _run_provision(
    company_name: str,
    subdomain: str,
    token: str,
    admin_username: str,
    admin_password: str,
    admin_telegram_id: int,
) -> dict:
    """Synchronous provision logic — runs in a thread via asyncio.to_thread."""
    import sys
    from pathlib import Path

    ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(ROOT))

    import bcrypt
    import socket
    from database.supabase import supabase

    def _hash_pw(plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

    def _is_port_free(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", port)) != 0

    # Generate company_id
    company_id = _slugify(company_name)[:40] or "company"
    check = supabase.table("companies").select("company_id").eq("company_id", company_id).execute()
    if check.data:
        company_id = f"{company_id}-{secrets.token_hex(3)}"

    # Find free port
    used_ports = {
        row["container_port"]
        for row in (supabase.table("companies").select("container_port").execute().data or [])
        if row.get("container_port")
    }
    port = 8100
    while not _is_port_free(port) or port in used_ports:
        port += 1

    # Insert company
    supabase.table("companies").insert({
        "company_id": company_id,
        "name": company_name,
        "plan": "trial",
        "subdomain": subdomain,
        "container_name": f"driftless-{subdomain}",
        "container_port": port,
        "is_active": True,
    }).execute()

    # Insert admin user
    supabase.table("users").insert({
        "username": admin_username,
        "full_name": admin_username,
        "role": "admin",
        "company_id": company_id,
        "password_hash": _hash_pw(admin_password),
        "telegram_id": admin_telegram_id if admin_telegram_id else None,
    }).execute()

    # Create deployment files + start Docker
    from scripts.provision import _create_deployment_files, _write_nginx_conf
    import subprocess

    auth_secret = secrets.token_hex(32)
    deploy_dir = _create_deployment_files(subdomain, company_id, token, port, auth_secret)

    compose_path = deploy_dir / "docker-compose.yml"
    subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        capture_output=True, text=True,
    )

    _write_nginx_conf(subdomain, port)

    return {"company_id": company_id, "subdomain": subdomain, "port": port}


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
async def register_form():
    """Serve the self-service registration form."""
    return HTMLResponse(content=_REGISTER_HTML)


class RegisterRequest(BaseModel):
    company_name: str
    admin_username: str
    admin_password: str
    admin_telegram_id: int = 0
    telegram_token: str


@router.post("/api/provision/register")
async def register(body: RegisterRequest):
    """Self-service company provisioning endpoint."""
    import asyncio
    from database.supabase import supabase

    # Validate inputs
    if not body.company_name.strip():
        return JSONResponse({"detail": "Tên công ty không được để trống."}, status_code=400)
    if len(body.admin_password) < 8:
        return JSONResponse({"detail": "Mật khẩu phải có ít nhất 8 ký tự."}, status_code=400)
    if not body.telegram_token.strip():
        return JSONResponse({"detail": "Telegram Bot Token không được để trống."}, status_code=400)

    # Validate Telegram bot token
    valid_token = await _validate_telegram_token(body.telegram_token.strip())
    if not valid_token:
        return JSONResponse(
            {"detail": "Telegram Bot Token không hợp lệ. Kiểm tra lại từ @BotFather."},
            status_code=400,
        )

    # Generate and check subdomain uniqueness
    subdomain = _slugify(body.company_name.strip())
    if not subdomain:
        return JSONResponse({"detail": "Tên công ty không hợp lệ."}, status_code=400)

    existing = supabase.table("companies").select("company_id").eq("subdomain", subdomain).execute()
    if existing.data:
        subdomain = f"{subdomain}-{secrets.token_hex(2)}"

    # Run provisioning in a background thread (blocking I/O)
    try:
        result = await asyncio.to_thread(
            _run_provision,
            body.company_name.strip(),
            subdomain,
            body.telegram_token.strip(),
            body.admin_username.strip(),
            body.admin_password,
            body.admin_telegram_id,
        )
    except Exception as e:
        return JSONResponse(
            {"detail": f"Lỗi khi khởi tạo: {e}"},
            status_code=500,
        )

    return {
        "subdomain": result["subdomain"],
        "webui_url": f"http://{result['subdomain']}.driftless.vn",
        "status": "provisioning",
    }

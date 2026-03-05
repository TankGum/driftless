from dotenv import load_dotenv
import os

load_dotenv()

# Prefer explicit TELEGRAM_TOKEN, but support BOT_TOKEN from portal onboarding flow.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

PORTAL_URL = os.getenv("PORTAL_URL", "")
PORTAL_API_KEY = os.getenv("PORTAL_API_KEY", "")
TENANT_ID = int(os.getenv("TENANT_ID", "0"))
COMPANY_NAME = os.getenv("COMPANY_NAME", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

# Zalo Bot config
ZALO_BOT_TOKEN = os.getenv("ZALO_BOT_TOKEN")

# Tesseract OCR — chỉ cần set trên Windows nếu Tesseract không trong PATH.
# Nếu env trỏ đến đường dẫn không tồn tại (ví dụ path Windows trong Linux container),
# bỏ qua để pytesseract tự dùng binary mặc định trong PATH.
_raw_tesseract_cmd = (os.getenv("TESSERACT_CMD") or "").strip()
if _raw_tesseract_cmd:
    if any(sep in _raw_tesseract_cmd for sep in ("/", "\\")):
        TESSERACT_CMD = _raw_tesseract_cmd if os.path.exists(_raw_tesseract_cmd) else None
    else:
        TESSERACT_CMD = _raw_tesseract_cmd
else:
    TESSERACT_CMD = None

# FastAPI server
BASE_URL = os.getenv("BASE_URL", "")  # e.g. https://your-domain.com

# Chainlit WebUI
CHAINLIT_ADMIN_PASSWORD = os.getenv("CHAINLIT_ADMIN_PASSWORD", "driftless2024")
DEFAULT_COMPANY_ID = os.getenv("DEFAULT_COMPANY_ID", "pilot")
TELEGRAM_RAG_FIRST = os.getenv("TELEGRAM_RAG_FIRST", "true").strip().lower() in {"1", "true", "yes", "on"}

# Chat history
CHAT_HISTORY_MAX_TURNS = int(os.getenv("CHAT_HISTORY_MAX_TURNS", "10"))
CHAT_SESSION_RETENTION_DAYS = int(os.getenv("CHAT_SESSION_RETENTION_DAYS", "7"))

# LangSmith monitoring (optional — set LANGCHAIN_TRACING_V2=true to enable)
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=<your_langsmith_key>
# LANGCHAIN_PROJECT=driftless

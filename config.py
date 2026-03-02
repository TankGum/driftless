from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
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

# Tesseract OCR — chỉ cần set trên Windows nếu Tesseract không trong PATH
# Linux VPS: để trống, pytesseract tự detect /usr/bin/tesseract
TESSERACT_CMD = os.getenv("TESSERACT_CMD")  # None nếu không set

# FastAPI server
BASE_URL = os.getenv("BASE_URL", "")  # e.g. https://your-domain.com

# Chainlit WebUI
CHAINLIT_ADMIN_PASSWORD = os.getenv("CHAINLIT_ADMIN_PASSWORD", "driftless2024")
DEFAULT_COMPANY_ID = os.getenv("DEFAULT_COMPANY_ID", "pilot")

# Chat history
CHAT_HISTORY_MAX_TURNS = int(os.getenv("CHAT_HISTORY_MAX_TURNS", "10"))
CHAT_SESSION_RETENTION_DAYS = int(os.getenv("CHAT_SESSION_RETENTION_DAYS", "7"))

# LangSmith monitoring (optional — set LANGCHAIN_TRACING_V2=true to enable)
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=<your_langsmith_key>
# LANGCHAIN_PROJECT=driftless

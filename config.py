from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

# Zalo Bot config
ZALO_BOT_TOKEN = os.getenv("ZALO_BOT_TOKEN")

# Tesseract OCR — chỉ cần set trên Windows nếu Tesseract không trong PATH
# Linux VPS: để trống, pytesseract tự detect /usr/bin/tesseract
TESSERACT_CMD = os.getenv("TESSERACT_CMD")  # None nếu không set

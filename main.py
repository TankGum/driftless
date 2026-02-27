"""Driftless — main entry point.

Starts the FastAPI server which hosts:
- Chainlit WebUI at /
- REST API at /api/*
- Telegram webhook at /webhook/telegram
- Zalo webhook at /webhook/zalo
- Health check at /health

To run:
    python main.py
    # or with auto-reload in dev:
    uvicorn main:app --reload --port 8000
"""
import uvicorn
from api.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

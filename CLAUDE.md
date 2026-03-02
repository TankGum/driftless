# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Driftless is a multi-tenant bot (Telegram + Zalo + WebUI) that serves as an internal AI agent for companies. It answers questions from company knowledge bases (Google Sheets/Docs/PDFs/uploaded files), provides analytics and forecasting on project data, handles employee onboarding, drafts documents, and manages anonymous feedback. The bot uses Claude AI (Anthropic) for natural language processing and Supabase as the database backend.

## Commands

```bash
# First-time setup (interactive — creates admin account and company)
python scripts/setup.py

# Run the server (FastAPI + Chainlit WebUI + Telegram + Zalo)
python main.py

# Dev mode with auto-reload
uvicorn main:app --reload --port 8000

# Manual sync of all document sources
python scripts/sync_sheets.py
```

There are no tests, linting, or build steps configured.

## Environment

Requires a `.env` file with: `TELEGRAM_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, `CLAUDE_API_KEY`, `GOOGLE_CREDENTIALS_PATH`. A `credentials.json` (Google service account) must also be present. Uses a Python venv at `.venv/`.

Optional env vars:
- `ZALO_BOT_TOKEN` — if absent, only Telegram runs.
- `BASE_URL` — public URL for Telegram webhook registration (e.g. `https://your-domain.com`).
- `CHAINLIT_ADMIN_PASSWORD` — password for Chainlit WebUI (default: `driftless2024`).
- `DEFAULT_COMPANY_ID` — fallback company (default: `pilot`).
- `TESSERACT_CMD` — path to Tesseract binary. On Linux, pytesseract auto-detects `/usr/bin/tesseract`. On Windows, set this if Tesseract is not in PATH (e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe`). Requires Tesseract binary + Vietnamese language pack installed on the OS.
- `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` — enables LangSmith monitoring.

## Architecture

**Entry point:** `python main.py` → uvicorn runs FastAPI (`api/app.py`). Chainlit WebUI is mounted at `/`. Telegram and Zalo run as polling threads. APScheduler handles hourly auto-sync.

**Request flow:**
- WebUI: `chainlit_app.py` → `pipeline/rag_chain.py` (LangChain LCEL) → domain modules
- REST API: `api/routers/*.py` → domain modules
- Telegram: `platforms/telegram/webhook.py` (polling thread) → `platforms/telegram/handlers.py` → domain modules
- Zalo: `platforms/zalo/webhook.py` (polling thread) → `platforms/zalo/handlers.py` → domain modules

**RAG pipeline (`pipeline/`):** LangChain LCEL chain with stages: `query_rewriter.py` (query rewrite) → `rag_chain.py` (hybrid search: vector + BM25 keyword) → `reranker.py` (cross-encoder `ms-marco-MiniLM-L-6-v2`, local, no API cost) → `guards.py` (retrieval guard: top rerank score < 0.3 → refuse without calling Claude) → generate answer.

**Intent routing:** Free-text messages go through `core/router.py` which uses keyword matching to classify into `KNOWLEDGE_QUERY`, `ANALYTICS_QUERY`, `FORECAST_QUERY`, or `SUPPORT_REQUEST`. Defaults to `KNOWLEDGE_QUERY` when no keywords match. Used by both platforms.

**Key modules:**

- **`api/`** — FastAPI application. `app.py` (factory, lifespan, middleware, mounts Chainlit). `deps.py` (dependency injection: auth, company_id). `routers/chat.py` (chat endpoint), `routers/upload.py` (file upload with content-hash dedup), `routers/admin.py` (admin operations).
- **`pipeline/`** — LangChain LCEL RAG pipeline. `rag_chain.py` (main chain), `query_rewriter.py`, `reranker.py` (cross-encoder), `guards.py` (retrieval guard with score threshold).
- **`chainlit_app.py`** — Chainlit WebUI. Username/password auth via bcrypt. File upload with content-hash dedup (asks user to confirm replace on duplicate content).
- **`platforms/telegram/`** — Telegram-specific handlers. `handlers.py` uses `python-telegram-bot` (`Update`, `ContextTypes`), Markdown parse mode, and `@safe_handler`/`@admin_only`/`@pm_or_above` decorators. `webhook.py` builds the Telegram application for polling.
- **`platforms/zalo/`** — Zalo-specific handlers. `handlers.py` uses `python-zalo-bot`. `formatter.py` strips Markdown to plain text (Zalo does not support Markdown). `webhook.py` builds the Zalo application for polling.
- **`knowledge/`** — Document indexing and retrieval. `source_manager.py` handles CRUD for data sources (Google Sheets/Docs URLs). `indexer.py` syncs documents into `document_chunks` in Supabase; `sync_local_file()` handles uploaded files with SHA256 content-hash dedup. `retriever.py` uses Claude for answer generation. `sheets_reader.py` reads Google Sheets, Docs, and PDFs via the Google API. `embedder.py` generates embeddings using fastembed (local multilingual model). For scanned/image PDFs, `sheets_reader.py` uses Tesseract OCR (PyMuPDF renders pages → pytesseract extracts text, supports Vietnamese).
- **`analytics/`** — `data_loader.py` reads live data from all active Google Sheets (matching tab names like "Project Progress", "KPI Tracking", "Team Performance"). `analyzer.py` sends the raw data to Claude Sonnet to answer analytics questions. **Token safety:** input capped at 200 rows/tab and 80k chars total to prevent cost explosion on large sheets.
- **`forecasting/`** — `engine.py` computes deadline risk, KPI miss risk, and team workload forecasts using rule-based logic on sheet data. `responder.py` wraps forecast data with Claude Sonnet for natural language answers. **Token safety:** input capped at 50 items/category and 30k chars total.
- **`support/`** — `drafter.py` (AI document drafting).
- **`core/`** — `auth.py` (user lookup by `telegram_id` or `zalo_id`), `decorators.py` (`@safe_handler`, `@admin_only`, `@pm_or_above` — Telegram-only), `router.py` (intent detection, platform-agnostic), `company.py` (multi-tenant company management with invite codes; Zalo variant `join_company_by_code_zalo()`), `orchestrator.py` (LangChain AgentExecutor + LangSmith tracing), `error_handler.py`, `logger.py`.
- **`jobs/auto_sync.py`** — Hourly auto-sync of all document sources across all active companies via APScheduler (async). Legacy Telegram callback retained for backwards compat.

**Multi-tenancy:** Each company has a `company_id`. Users belong to a company. Data sources, documents, and feedbacks are scoped by `company_id`. The default/fallback is `"pilot"`.

**Portal login flow (Chainlit WebUI in tenant containers):** `core/chainlit_data_layer.py` handles Chainlit's data persistence. `_company_id()` resolves the active company via `TENANT_ID` (injected by portal at container start) — `str(TENANT_ID)` when `TENANT_ID > 0`, falling back to `DEFAULT_COMPANY_ID or "pilot"`. On first portal login, `create_user()` auto-inserts a record into the `users` table using `user.metadata` (populated by `auth_callback` with `full_name`, `role`); subsequent logins return the existing record. This ensures Chainlit never returns "not found" after a successful portal auth.

**Roles:** Three roles — `admin`, `pm`, `member`. In Telegram, enforced via decorators. In Zalo, checked inline in each handler. In WebUI/API, checked via `api/deps.py`. Admin-only: add/remove docs, resync, view feedback, set roles. PM+Admin: summary, risk alerts, list docs, sync status, file upload.

**Supabase tables:** `users`, `companies`, `data_sources`, `documents`, `document_chunks`, `onboarding_progress`, `feedbacks`.

- `users` has both `telegram_id` (nullable) and `zalo_id` (nullable) columns plus `username`/`password_hash` for WebUI auth.
- `onboarding_progress` has both `telegram_id` (nullable) and `zalo_id` (nullable) columns.
- `data_sources` has `last_synced` (TIMESTAMPTZ, nullable) and `content_hash` (TEXT, nullable — SHA256 of file content for dedup) columns.

**Content-hash dedup:** When uploading files, `indexer.py` computes SHA256 of the extracted text. If a different-named file with the same hash already exists, the upload is flagged as duplicate. In Chainlit WebUI, user is prompted to replace or keep. In API, caller can pass `?replace=true`. After migration, run `NOTIFY pgrst, 'reload schema';` in Supabase SQL Editor to refresh PostgREST schema cache.

**Claude models used:** `claude-sonnet-4-6` for answer generation (knowledge, analytics, forecasting, drafting). `claude-haiku-4-5-20251001` for lightweight tasks (chunk ranking, feedback categorization).

**Embedding model:** `intfloat/multilingual-e5-large` (dim=1024) via fastembed.

**Reranker model:** `cross-encoder/ms-marco-MiniLM-L-6-v2` — runs locally, no API cost.

## Conventions

- All user-facing text is in Vietnamese. Zalo responses use plain Vietnamese (no diacritics in some places due to Zalo plain-text limitation).
- Telegram messages use Markdown parse mode. Zalo messages are plain text — always pass through `zalo.formatter.strip_markdown()` before sending.
- Google Sheets/Docs/PDFs are the primary external data sources; the bot reads them via a service account. Scanned PDFs use Tesseract OCR. Users can also upload local files (PDF, DOCX, TXT) via WebUI or API.
- No ORM — direct Supabase client calls (`supabase.table(...).select/insert/update/delete`).
- Domain modules (`knowledge/`, `analytics/`, `forecasting/`, `support/drafter.py`) are fully platform-agnostic — they take plain `str`/`dict` and return plain `str`. Never add Telegram, Zalo, or Chainlit imports to these modules.
- `knowledge/indexer.py` `sync_local_file()` returns a 3-tuple `(bool, str, dict | None)` — callers must unpack all three values.
- After adding columns to Supabase, run `NOTIFY pgrst, 'reload schema';` in SQL Editor to refresh PostgREST's schema cache — otherwise the API silently ignores new columns.

## Database Migrations

Migration file: `scripts/migrate.sql` — idempotent, safe to run multiple times.

For existing deployments, new columns use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` placed right after the corresponding `CREATE TABLE` block. After running migrations, always reload PostgREST schema cache:
```sql
NOTIFY pgrst, 'reload schema';
```

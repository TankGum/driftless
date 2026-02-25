# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Driftless is a multi-tenant bot (Telegram + Zalo) that serves as an internal AI agent for companies. It answers questions from company knowledge bases (Google Sheets/Docs), provides analytics and forecasting on project data, handles employee onboarding, drafts documents, and manages anonymous feedback. The bot uses Claude AI (Anthropic) for natural language processing and Supabase as the database backend.

## Commands

```bash
# First-time setup (interactive — creates admin account and company)
python scripts/setup.py

# Run the bot (starts both Telegram and Zalo simultaneously)
python main.py

# Manual sync of all document sources
python scripts/sync_sheets.py
```

There are no tests, linting, or build steps configured.

## Environment

Requires a `.env` file with: `TELEGRAM_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, `CLAUDE_API_KEY`, `GOOGLE_CREDENTIALS_PATH`, `ZALO_BOT_TOKEN`. A `credentials.json` (Google service account) must also be present. Uses a Python venv at `.venv/`.

`ZALO_BOT_TOKEN` is optional — if absent, only Telegram runs.

## Architecture

**Dual-platform design:** Both Telegram and Zalo bots call the same domain modules. `main.py` starts Telegram in the main thread (via `run_polling()`) and Zalo in a daemon thread. All domain logic is platform-agnostic.

**Request flow:**
- Telegram: `main.py` -> `platforms/telegram/handlers.py` -> domain modules
- Zalo: `main.py` (thread) → `platforms/zalo/handlers.py` → same domain modules

**Intent routing:** Free-text messages go through `core/router.py` which uses keyword matching to classify into `KNOWLEDGE_QUERY`, `ANALYTICS_QUERY`, `FORECAST_QUERY`, or `SUPPORT_REQUEST`. Defaults to `KNOWLEDGE_QUERY` when no keywords match. Used by both platforms.

**Key modules:**

- **`platforms/telegram/`** — Telegram-specific handlers. `handlers.py` uses `python-telegram-bot` (`Update`, `ContextTypes`), Markdown parse mode, and `@safe_handler`/`@admin_only`/`@pm_or_above` decorators.
- **`platforms/zalo/`** — Zalo-specific handlers. `handlers.py` uses `python-zalo-bot` (same API pattern as python-telegram-bot). `formatter.py` strips Markdown to plain text (Zalo does not support Markdown). Zalo commands use text-prefix matching; Zalo-specific user identity is stored in `zalo_id` column.
- **`knowledge/`** — RAG pipeline over company documents. `source_manager.py` handles CRUD for data sources (Google Sheets/Docs URLs). `indexer.py` syncs documents into `document_chunks` in Supabase. `retriever.py` uses Claude Haiku to rank chunks by relevance, then Claude Sonnet to generate answers. `sheets_reader.py` reads Google Sheets and Docs via the Google API.
- **`analytics/`** — `data_loader.py` reads live data from all active Google Sheets (matching tab names like "Project Progress", "KPI Tracking", "Team Performance"). `analyzer.py` sends the raw data to Claude Sonnet to answer analytics questions.
- **`forecasting/`** — `engine.py` computes deadline risk, KPI miss risk, and team workload forecasts using rule-based logic on sheet data. `responder.py` wraps forecast data with Claude Sonnet for natural language answers.
- **`support/`** — `onboarding.py` (step-based onboarding; Telegram variant uses `telegram_id`, Zalo variant uses `zalo_id` via `*_zalo()` functions), `drafter.py` (AI document drafting), `feedback.py` (anonymous feedback with AI categorization), `task_helper.py` (task lookup by owner name).
- **`core/`** — `auth.py` (user lookup by `telegram_id` or `zalo_id`), `decorators.py` (`@safe_handler`, `@admin_only`, `@pm_or_above` — Telegram-only), `router.py` (intent detection, platform-agnostic), `company.py` (multi-tenant company management with invite codes; Zalo variant `join_company_by_code_zalo()`), `error_handler.py`, `logger.py`.
- **`jobs/auto_sync.py`** — Hourly auto-sync of all document sources across all active companies via Telegram's job queue.

**Multi-tenancy:** Each company has a `company_id`. Users belong to a company. Data sources, documents, and feedbacks are scoped by `company_id`. The default/fallback is `"pilot"`.

**Roles:** Three roles — `admin`, `pm`, `member`. In Telegram, enforced via decorators. In Zalo, checked inline in each handler. Admin-only: add/remove docs, resync, view feedback, set roles. PM+Admin: summary, risk alerts, list docs, sync status.

**Supabase tables:** `users`, `companies`, `data_sources`, `documents`, `document_chunks`, `onboarding_progress`, `feedbacks`.

- `users` has both `telegram_id` (nullable) and `zalo_id` (nullable) columns. Both are NOT NULL-free; a user row will have one or the other set depending on platform.
- `onboarding_progress` has both `telegram_id` (nullable) and `zalo_id` (nullable) columns.
- `data_sources` has `last_synced` (TIMESTAMPTZ, nullable) column.

**Claude models used:** `claude-sonnet-4-6` for answer generation (knowledge, analytics, forecasting, drafting). `claude-haiku-4-5-20251001` for lightweight tasks (chunk ranking, feedback categorization).

## Conventions

- All user-facing text is in Vietnamese. Zalo responses use plain Vietnamese (no diacritics in some places due to Zalo plain-text limitation).
- Telegram messages use Markdown parse mode. Zalo messages are plain text — always pass through `zalo.formatter.strip_markdown()` before sending.
- Google Sheets/Docs are the primary external data sources; the bot reads them via a service account.
- No ORM — direct Supabase client calls (`supabase.table(...).select/insert/update/delete`).
- Domain modules (`knowledge/`, `analytics/`, `forecasting/`, `support/drafter.py`, `support/feedback.py`, `support/task_helper.py`) are fully platform-agnostic — they take plain `str`/`dict` and return plain `str`. Never add Telegram or Zalo imports to these modules.



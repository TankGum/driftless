-- ============================================
-- DRIFTLESS - Database Setup (single file)
-- Fresh setup: run this once in Supabase SQL Editor
-- Safe to run multiple times (idempotent)
-- ============================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- COMPANIES
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
  id                  bigserial   PRIMARY KEY,
  company_id          text        UNIQUE NOT NULL,
  name                text        NOT NULL,
  telegram_group_id   text,
  admin_telegram_id   bigint,
  invite_code         text,
  is_active           boolean     DEFAULT true,
  created_at          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_companies_company_id ON companies(company_id);

-- ============================================
-- USERS (multi-platform identity)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
  id            bigserial   PRIMARY KEY,
  telegram_id   bigint,
  zalo_id       text,
  username      text,
  full_name     text,
  role          text        DEFAULT 'member',
  company_id    text        DEFAULT 'default',
  password_hash text,
  created_at    timestamptz DEFAULT now()
);

-- Partial unique indexes so NULL values are allowed on both columns
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_telegram_id
  ON users(telegram_id) WHERE telegram_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_zalo_id
  ON users(zalo_id) WHERE zalo_id IS NOT NULL;

-- Username must be unique within a company (required for Chainlit login)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_company
  ON users(username, company_id);

CREATE INDEX IF NOT EXISTS idx_users_company   ON users(company_id);
CREATE INDEX IF NOT EXISTS idx_users_telegram  ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_zalo      ON users(zalo_id);

-- ============================================
-- DATA SOURCES
-- ============================================
CREATE TABLE IF NOT EXISTS data_sources (
  id           bigserial   PRIMARY KEY,
  company_id   text        NOT NULL,
  source_type  text        NOT NULL,
  source_id    text        NOT NULL,
  title        text,
  added_by     text,
  is_active    boolean     DEFAULT true,
  created_at   timestamptz DEFAULT now(),
  last_synced  timestamptz,
  content_hash text,
  UNIQUE (company_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_data_sources_company ON data_sources(company_id);

-- Add content_hash to existing deployments (no-op on fresh installs)
ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS content_hash text;

-- ============================================
-- DOCUMENTS
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
  id          bigserial   PRIMARY KEY,
  company_id  text        NOT NULL,
  source_type text,
  source_id   text,
  sheet_name  text,
  title       text,
  last_synced timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_source  ON documents(source_id);

-- ============================================
-- DOCUMENT CHUNKS
-- ============================================
CREATE TABLE IF NOT EXISTS document_chunks (
  id          bigserial   PRIMARY KEY,
  document_id bigint      REFERENCES documents(id) ON DELETE CASCADE,
  content     text        NOT NULL,
  embedding   vector(1024),
  row_number  int,
  metadata    jsonb,
  fts_content tsvector    GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED,
  created_at  timestamptz DEFAULT now()
);

-- Vector similarity index (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
  ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_chunks_fts
  ON document_chunks USING GIN(fts_content);

-- ============================================
-- CHAT MESSAGES (persistent history)
-- ============================================
CREATE TABLE IF NOT EXISTS chat_messages (
  id          bigserial   PRIMARY KEY,
  company_id  text        NOT NULL,
  user_key    text        NOT NULL,
  platform    text        NOT NULL,  -- 'telegram', 'zalo', 'chainlit'
  role        text        NOT NULL,  -- 'user' or 'assistant'
  content     text        NOT NULL,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_lookup
  ON chat_messages(company_id, user_key, created_at DESC);

-- Add platform column to existing deployments (no-op on fresh installs)
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS platform text;

-- ============================================
-- CHAT SESSIONS (Chainlit WebUI only)
-- ============================================
CREATE TABLE IF NOT EXISTS chat_sessions (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id  text        NOT NULL,
  user_key    text        NOT NULL,
  title       text,               -- auto-set từ tin nhắn đầu (50 chars)
  is_pinned   boolean     DEFAULT false,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_lookup
  ON chat_sessions(company_id, user_key, is_pinned DESC, created_at DESC);

-- Add session_id to chat_messages (NULL = legacy messages from Telegram/Zalo)
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS session_id uuid
  REFERENCES chat_sessions(id) ON DELETE CASCADE;

-- ============================================
-- KEYWORD SEARCH RPC FUNCTION
-- Used by pipeline/rag_chain.py for BM25-style retrieval
-- ============================================
CREATE OR REPLACE FUNCTION keyword_search_chunks(
  query_text        text,
  filter_company_id text,
  match_count       int DEFAULT 20
)
RETURNS TABLE (
  id          bigint,
  content     text,
  document_id bigint,
  metadata    jsonb,
  title       text,
  source_id   text
)
LANGUAGE sql
AS $$
  SELECT
    dc.id,
    dc.content,
    dc.document_id,
    dc.metadata,
    coalesce(dc.metadata->>'title', '')     AS title,
    coalesce(dc.metadata->>'source_id', '') AS source_id
  FROM document_chunks dc
  JOIN documents d ON d.id = dc.document_id
  WHERE d.company_id = filter_company_id
    AND dc.fts_content @@ plainto_tsquery('simple', query_text)
  ORDER BY ts_rank(dc.fts_content, plainto_tsquery('simple', query_text)) DESC
  LIMIT match_count;
$$;

-- ============================================
-- SEED: default company (fresh setup)
-- ============================================
INSERT INTO companies (company_id, name, admin_telegram_id, is_active)
VALUES ('default', 'Default Company', 0, true)
ON CONFLICT (company_id) DO NOTHING;

-- ============================================
-- Done. Next steps:
--   python scripts/setup.py   → create admin account + company
--   python main.py            → start the bot
-- ============================================

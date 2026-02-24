-- ============================================
-- DRIFTLESS — Database Migration
-- Chạy file này 1 lần khi setup project mới
-- ============================================

-- Enable vector extension
create extension if not exists vector;

-- ── USERS ──────────────────────────────────
create table if not exists users (
  id bigserial primary key,
  telegram_id bigint unique not null,
  username text,
  full_name text,
  role text default 'member',
  company_id text default 'default',
  created_at timestamp default now()
);

-- ── COMPANIES ──────────────────────────────
create table if not exists companies (
  id bigserial primary key,
  company_id text unique not null,
  name text not null,
  telegram_group_id text,
  admin_telegram_id bigint,
  invite_code text,
  is_active bool default true,
  created_at timestamp default now()
);

-- ── DATA SOURCES ───────────────────────────
create table if not exists data_sources (
  id bigserial primary key,
  company_id text not null,
  source_type text not null,
  source_id text not null,
  title text,
  added_by bigint,
  is_active bool default true,
  created_at timestamp default now(),
  unique(company_id, source_id)
);

alter table data_sources add column if not exists last_synced timestamp;

-- ── DOCUMENTS ──────────────────────────────
create table if not exists documents (
  id bigserial primary key,
  company_id text not null,
  source_type text,
  source_id text,
  sheet_name text,
  title text,
  last_synced timestamp default now()
);

-- ── DOCUMENT CHUNKS ────────────────────────
create table if not exists document_chunks (
  id bigserial primary key,
  document_id bigint references documents(id) on delete cascade,
  content text not null,
  embedding vector(1536),
  row_number int,
  metadata jsonb,
  created_at timestamp default now()
);

create index if not exists idx_document_chunks_embedding 
on document_chunks using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

-- ── ONBOARDING ─────────────────────────────
create table if not exists onboarding_progress (
  id bigserial primary key,
  telegram_id bigint references users(telegram_id) on delete cascade,
  step int default 0,
  completed_steps jsonb default '[]',
  started_at timestamp default now(),
  completed_at timestamp
);

-- ── FEEDBACKS ──────────────────────────────
create table if not exists feedbacks (
  id bigserial primary key,
  company_id text not null,
  content text not null,
  category text,
  status text default 'new',
  created_at timestamp default now()
);

-- ── REMINDERS ──────────────────────────────
create table if not exists reminders (
  id bigserial primary key,
  telegram_id bigint references users(telegram_id) on delete cascade,
  content text not null,
  remind_at timestamp not null,
  sent bool default false,
  created_at timestamp default now()
);

-- ── INDEXES ────────────────────────────────
create index if not exists idx_users_company on users(company_id);
create index if not exists idx_users_telegram on users(telegram_id);
create index if not exists idx_data_sources_company on data_sources(company_id);
create index if not exists idx_documents_company on documents(company_id);
create index if not exists idx_documents_source on documents(source_id);
create index if not exists idx_feedbacks_company on feedbacks(company_id);
create index if not exists idx_reminders_sent on reminders(sent, remind_at);

-- ── DEFAULT COMPANY ────────────────────────
insert into companies (company_id, name, admin_telegram_id)
values ('default', 'Default Company', 0)
on conflict (company_id) do nothing;

-- ============================================
-- Done! Database is ready.
-- ============================================

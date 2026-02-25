-- ============================================
-- DRIFTLESS - Database migration (Telegram + Zalo)
-- Safe to run many times (idempotent)
-- ============================================

create extension if not exists vector;

-- COMPANIES
create table if not exists companies (
  id bigserial primary key,
  company_id text unique not null,
  name text not null,
  telegram_group_id text,
  admin_telegram_id bigint,
  invite_code text,
  is_active boolean default true,
  created_at timestamptz default now()
);

alter table if exists companies add column if not exists telegram_group_id text;
alter table if exists companies add column if not exists admin_telegram_id bigint;
alter table if exists companies add column if not exists invite_code text;
alter table if exists companies add column if not exists is_active boolean default true;

-- USERS (multi-platform identity)
create table if not exists users (
  id bigserial primary key,
  telegram_id bigint,
  zalo_id text,
  username text,
  full_name text,
  role text default 'member',
  company_id text default 'default',
  created_at timestamptz default now()
);

alter table if exists users add column if not exists telegram_id bigint;
alter table if exists users add column if not exists zalo_id text;
alter table if exists users add column if not exists username text;
alter table if exists users add column if not exists full_name text;
alter table if exists users add column if not exists role text default 'member';
alter table if exists users add column if not exists company_id text default 'default';
alter table if exists users add column if not exists created_at timestamptz default now();
alter table if exists users alter column telegram_id drop not null;
update users set company_id = 'default' where company_id is null;
update users set role = 'member' where role is null;

create unique index if not exists uq_users_telegram_id
  on users(telegram_id) where telegram_id is not null;
create unique index if not exists uq_users_zalo_id
  on users(zalo_id) where zalo_id is not null;
create index if not exists idx_users_company on users(company_id);
create index if not exists idx_users_telegram on users(telegram_id);
create index if not exists idx_users_zalo on users(zalo_id);

-- DATA SOURCES
create table if not exists data_sources (
  id bigserial primary key,
  company_id text not null,
  source_type text not null,
  source_id text not null,
  title text,
  added_by text,
  is_active boolean default true,
  created_at timestamptz default now(),
  last_synced timestamptz,
  unique(company_id, source_id)
);

alter table if exists data_sources add column if not exists company_id text;
alter table if exists data_sources add column if not exists source_type text;
alter table if exists data_sources add column if not exists source_id text;
alter table if exists data_sources add column if not exists title text;
alter table if exists data_sources add column if not exists added_by text;
alter table if exists data_sources add column if not exists is_active boolean default true;
alter table if exists data_sources add column if not exists created_at timestamptz default now();
alter table if exists data_sources add column if not exists last_synced timestamptz;
alter table if exists data_sources alter column added_by type text using added_by::text;
create index if not exists idx_data_sources_company on data_sources(company_id);

-- DOCUMENTS
create table if not exists documents (
  id bigserial primary key,
  company_id text not null,
  source_type text,
  source_id text,
  sheet_name text,
  title text,
  last_synced timestamptz default now()
);

alter table if exists documents add column if not exists company_id text;
alter table if exists documents add column if not exists source_type text;
alter table if exists documents add column if not exists source_id text;
alter table if exists documents add column if not exists sheet_name text;
alter table if exists documents add column if not exists title text;
alter table if exists documents add column if not exists last_synced timestamptz default now();
create index if not exists idx_documents_company on documents(company_id);
create index if not exists idx_documents_source on documents(source_id);

-- DOCUMENT CHUNKS
create table if not exists document_chunks (
  id bigserial primary key,
  document_id bigint references documents(id) on delete cascade,
  content text not null,
  embedding vector(1536),
  row_number int,
  metadata jsonb,
  created_at timestamptz default now()
);

alter table if exists document_chunks add column if not exists document_id bigint references documents(id) on delete cascade;
alter table if exists document_chunks add column if not exists content text;
alter table if exists document_chunks add column if not exists embedding vector(1536);
alter table if exists document_chunks add column if not exists row_number int;
alter table if exists document_chunks add column if not exists metadata jsonb;
alter table if exists document_chunks add column if not exists created_at timestamptz default now();

create index if not exists idx_document_chunks_embedding
  on document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ONBOARDING
create table if not exists onboarding_progress (
  id bigserial primary key,
  telegram_id bigint,
  zalo_id text,
  step int default 0,
  completed_steps jsonb default '[]'::jsonb,
  started_at timestamptz default now(),
  completed_at timestamptz
);

alter table if exists onboarding_progress add column if not exists telegram_id bigint;
alter table if exists onboarding_progress add column if not exists zalo_id text;
alter table if exists onboarding_progress add column if not exists step int default 0;
alter table if exists onboarding_progress add column if not exists completed_steps jsonb default '[]'::jsonb;
alter table if exists onboarding_progress add column if not exists started_at timestamptz default now();
alter table if exists onboarding_progress add column if not exists completed_at timestamptz;
create index if not exists idx_onboarding_telegram on onboarding_progress(telegram_id);
create index if not exists idx_onboarding_zalo on onboarding_progress(zalo_id);

-- FEEDBACKS
create table if not exists feedbacks (
  id bigserial primary key,
  company_id text not null,
  content text not null,
  category text,
  status text default 'new',
  created_at timestamptz default now()
);

alter table if exists feedbacks add column if not exists company_id text;
alter table if exists feedbacks add column if not exists content text;
alter table if exists feedbacks add column if not exists category text;
alter table if exists feedbacks add column if not exists status text default 'new';
alter table if exists feedbacks add column if not exists created_at timestamptz default now();
create index if not exists idx_feedbacks_company on feedbacks(company_id);

-- REMINDERS
create table if not exists reminders (
  id bigserial primary key,
  telegram_id bigint,
  zalo_id text,
  content text not null,
  remind_at timestamptz not null,
  sent boolean default false,
  created_at timestamptz default now()
);

alter table if exists reminders add column if not exists telegram_id bigint;
alter table if exists reminders add column if not exists zalo_id text;
alter table if exists reminders add column if not exists content text;
alter table if exists reminders add column if not exists remind_at timestamptz;
alter table if exists reminders add column if not exists sent boolean default false;
alter table if exists reminders add column if not exists created_at timestamptz default now();
create index if not exists idx_reminders_sent on reminders(sent, remind_at);

-- DEFAULT COMPANY
insert into companies (company_id, name, admin_telegram_id, is_active)
values ('default', 'Default Company', 0, true)
on conflict (company_id) do nothing;

-- ============================================
-- Done
-- ============================================

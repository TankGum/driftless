-- ============================================
-- DRIFTLESS - Reset all runtime data
-- WARNING: This removes all rows in app tables.
-- ============================================

truncate table document_chunks restart identity cascade;
truncate table documents restart identity cascade;
truncate table data_sources restart identity cascade;
truncate table users restart identity cascade;
truncate table companies restart identity cascade;

insert into companies (company_id, name, admin_telegram_id, is_active)
values ('default', 'Default Company', 0, true)
on conflict (company_id) do nothing;

-- After reset:
-- 1) run scripts/migrate.sql in Supabase SQL Editor
-- 2) python scripts/setup.py  → create admin + company
-- 3) python main.py           → start the bot
-- 4) add docs again with /adddoc

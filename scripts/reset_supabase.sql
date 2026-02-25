-- ============================================
-- DRIFTLESS - Reset all runtime data
-- WARNING: This removes all rows in app tables.
-- ============================================

truncate table document_chunks restart identity cascade;
truncate table documents restart identity cascade;
truncate table data_sources restart identity cascade;
truncate table onboarding_progress restart identity cascade;
truncate table feedbacks restart identity cascade;
truncate table reminders restart identity cascade;
truncate table users restart identity cascade;
truncate table companies restart identity cascade;

insert into companies (company_id, name, admin_telegram_id, is_active)
values ('default', 'Default Company', 0, true)
on conflict (company_id) do nothing;

-- After reset:
-- 1) run scripts/migrate.sql
-- 2) run python scripts/setup.py to create admin + company
-- 3) add docs again with /adddoc

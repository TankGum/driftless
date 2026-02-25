-- Driftless v2 Migration
-- DB chỉ lưu user/company, data đọc live từ Drive

-- Thêm drive_folder_id cho company
ALTER TABLE companies ADD COLUMN IF NOT EXISTS drive_folder_id TEXT;

-- Thêm thông tin cá nhân user
ALTER TABLE users ADD COLUMN IF NOT EXISTS department TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS position TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;

-- Chạy sau khi deploy code mới:
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS data_sources CASCADE;
DROP TABLE IF EXISTS onboarding_progress CASCADE;
DROP TABLE IF EXISTS feedbacks CASCADE;

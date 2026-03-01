ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';

UPDATE users
SET role = 'user'
WHERE role IS NULL OR role = '';

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

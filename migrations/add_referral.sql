-- Add referral tracking to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS referred_by text;

-- Index for fast lookup of who referred whom
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);

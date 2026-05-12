-- 004 features
ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_referrer_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_credited BOOLEAN DEFAULT FALSE;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS last_post_at TIMESTAMPTZ;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS invite_link TEXT;
INSERT INTO platform_settings (key, value, value_type, description) VALUES
('force_sub_channel', '', 'string', 'Force sub channel'),
('force_sub_enabled', 'false', 'boolean', 'Require force-sub for referral reward'),
('min_subscriber_count', '100', 'integer', 'Minimum subs to list a channel'),
('inactive_days_remove', '30', 'integer', 'Auto-remove channels with no posts for N days')
ON CONFLICT (key) DO NOTHING;

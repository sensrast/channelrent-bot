-- 006 join request auto-accept + welcome DM
INSERT INTO platform_settings (key, value, value_type, description) VALUES
('join_request_auto_accept', 'false', 'boolean', 'Auto-accept channel join requests and send welcome DM'),
('welcome_dm_message', '👋 Welcome! Thanks for joining. We''re glad to have you here.', 'string', 'Welcome DM sent on auto-accept of join requests')
ON CONFLICT (key) DO NOTHING;

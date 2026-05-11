-- Ensures soft-delete column on channels (idempotent)
ALTER TABLE channels ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
UPDATE channels SET is_active=TRUE WHERE is_active IS NULL;

-- Pricing-engine config keys (safe inserts)
INSERT INTO platform_settings (key, value, updated_at) VALUES
  ('base_price_per_post_credits','5',NOW()),
  ('price_per_1k_subscribers','2',NOW()),
  ('price_per_100_views','1',NOW()),
  ('activity_multiplier_high','1.5',NOW()),
  ('activity_multiplier_medium','1.0',NOW()),
  ('activity_multiplier_low','0.7',NOW()),
  ('min_listing_price','1',NOW()),
  ('max_listing_price','10000',NOW()),
  ('watermark_enabled','true',NOW()),
  ('marketplace_enabled','true',NOW()),
  ('maintenance_mode','false',NOW())
ON CONFLICT (key) DO NOTHING;

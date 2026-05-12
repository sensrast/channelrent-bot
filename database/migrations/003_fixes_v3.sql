-- Migration v3: fractional credits + watermark text + channel reports
ALTER TABLE users
    ALTER COLUMN credits_balance TYPE NUMERIC(14,2) USING credits_balance::NUMERIC(14,2),
    ALTER COLUMN credits_total_purchased TYPE NUMERIC(14,2) USING credits_total_purchased::NUMERIC(14,2),
    ALTER COLUMN credits_total_spent TYPE NUMERIC(14,2) USING credits_total_spent::NUMERIC(14,2),
    ALTER COLUMN credits_total_refunded TYPE NUMERIC(14,2) USING credits_total_refunded::NUMERIC(14,2),
    ALTER COLUMN earnings_pending TYPE NUMERIC(14,2) USING earnings_pending::NUMERIC(14,2),
    ALTER COLUMN earnings_paid TYPE NUMERIC(14,2) USING earnings_paid::NUMERIC(14,2);
ALTER TABLE bookings
    ALTER COLUMN total_credits_charged TYPE NUMERIC(14,2) USING total_credits_charged::NUMERIC(14,2),
    ALTER COLUMN credits_used TYPE NUMERIC(14,2) USING credits_used::NUMERIC(14,2),
    ALTER COLUMN credits_refunded TYPE NUMERIC(14,2) USING credits_refunded::NUMERIC(14,2),
    ALTER COLUMN platform_commission_credits TYPE NUMERIC(14,2) USING platform_commission_credits::NUMERIC(14,2),
    ALTER COLUMN owner_earnings_credits TYPE NUMERIC(14,2) USING owner_earnings_credits::NUMERIC(14,2);
ALTER TABLE credit_transactions
    ALTER COLUMN amount TYPE NUMERIC(14,2) USING amount::NUMERIC(14,2),
    ALTER COLUMN balance_before TYPE NUMERIC(14,2) USING balance_before::NUMERIC(14,2),
    ALTER COLUMN balance_after TYPE NUMERIC(14,2) USING balance_after::NUMERIC(14,2);
INSERT INTO platform_settings (key, value, updated_at) VALUES ('watermark_text','📢 Promoted via ChannelRent', NOW()) ON CONFLICT (key) DO NOTHING;
CREATE TABLE IF NOT EXISTS channel_reports (report_id BIGSERIAL PRIMARY KEY, channel_id BIGINT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE, reporter_id BIGINT NOT NULL REFERENCES users(user_id), reason TEXT NOT NULL, status VARCHAR(20) DEFAULT 'open', created_at TIMESTAMPTZ DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_reports_channel ON channel_reports(channel_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON channel_reports(status);

-- 005 precision: support fractional credits (e.g. 1.667 cr for 10 min @ 10 cr/hr)
ALTER TABLE users ALTER COLUMN credits_balance TYPE NUMERIC(20,4) USING credits_balance::numeric;
ALTER TABLE users ALTER COLUMN credits_total_purchased TYPE NUMERIC(20,4) USING credits_total_purchased::numeric;
ALTER TABLE users ALTER COLUMN credits_total_spent TYPE NUMERIC(20,4) USING credits_total_spent::numeric;
ALTER TABLE users ALTER COLUMN credits_total_refunded TYPE NUMERIC(20,4) USING credits_total_refunded::numeric;
ALTER TABLE users ALTER COLUMN earnings_pending TYPE NUMERIC(20,4) USING earnings_pending::numeric;
ALTER TABLE users ALTER COLUMN earnings_paid TYPE NUMERIC(20,4) USING earnings_paid::numeric;
ALTER TABLE bookings ALTER COLUMN total_credits_charged TYPE NUMERIC(20,4) USING total_credits_charged::numeric;
ALTER TABLE bookings ALTER COLUMN credits_used TYPE NUMERIC(20,4) USING credits_used::numeric;
ALTER TABLE bookings ALTER COLUMN credits_refunded TYPE NUMERIC(20,4) USING credits_refunded::numeric;
ALTER TABLE bookings ALTER COLUMN platform_commission_credits TYPE NUMERIC(20,4) USING platform_commission_credits::numeric;
ALTER TABLE bookings ALTER COLUMN owner_earnings_credits TYPE NUMERIC(20,4) USING owner_earnings_credits::numeric;
ALTER TABLE credit_transactions ALTER COLUMN amount TYPE NUMERIC(20,4) USING amount::numeric;
ALTER TABLE credit_transactions ALTER COLUMN balance_before TYPE NUMERIC(20,4) USING balance_before::numeric;
ALTER TABLE credit_transactions ALTER COLUMN balance_after TYPE NUMERIC(20,4) USING balance_after::numeric;
ALTER TABLE channels ALTER COLUMN total_revenue_credits TYPE NUMERIC(20,4) USING total_revenue_credits::numeric;

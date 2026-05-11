-- ChannelRent complete schema
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_owner BOOLEAN DEFAULT FALSE,
    is_advertiser BOOLEAN DEFAULT FALSE,
    is_banned BOOLEAN DEFAULT FALSE,
    ban_reason TEXT,
    credits_balance BIGINT DEFAULT 0,
    credits_total_purchased BIGINT DEFAULT 0,
    credits_total_spent BIGINT DEFAULT 0,
    credits_total_refunded BIGINT DEFAULT 0,
    earnings_pending BIGINT DEFAULT 0,
    earnings_paid BIGINT DEFAULT 0,
    total_bookings_made INTEGER DEFAULT 0,
    total_bookings_received INTEGER DEFAULT 0,
    total_channels_listed INTEGER DEFAULT 0,
    language_code VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW(),
    referred_by BIGINT REFERENCES users(user_id),
    referral_code VARCHAR(20) UNIQUE,
    referral_count INTEGER DEFAULT 0,
    upi_id VARCHAR(255),
    upi_verified BOOLEAN DEFAULT FALSE,
    has_blocked_bot BOOLEAN DEFAULT FALSE,
    reliability_strikes INTEGER DEFAULT 0,
    notify_new_booking BOOLEAN DEFAULT TRUE,
    notify_post_live BOOLEAN DEFAULT TRUE,
    notify_post_deleted BOOLEAN DEFAULT TRUE,
    notify_payment_received BOOLEAN DEFAULT TRUE,
    notify_credits_low BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_users_owner ON users(is_owner);
CREATE INDEX IF NOT EXISTS idx_users_advertiser ON users(is_advertiser);
CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
CREATE INDEX IF NOT EXISTS idx_users_referral ON users(referral_code);

CREATE TABLE IF NOT EXISTS channel_categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    emoji VARCHAR(10) DEFAULT '📢',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    channel_count INTEGER DEFAULT 0
);

INSERT INTO channel_categories (name, emoji, description, sort_order) VALUES
('Technology', '💻', 'Tech news, gadgets, software', 1),
('Crypto & Finance', '₿', 'Crypto, stocks, trading, finance', 2),
('Education', '📚', 'Courses, tutorials, learning', 3),
('Entertainment', '🎬', 'Movies, music, fun content', 4),
('News', '📰', 'News, current affairs, updates', 5),
('Gaming', '🎮', 'Games, esports, gaming news', 6),
('Health & Fitness', '💪', 'Health, wellness, fitness tips', 7),
('Business', '💼', 'Business, entrepreneurship, startups', 8),
('Lifestyle', '✨', 'Fashion, food, travel, lifestyle', 9),
('Sports', '⚽', 'Sports news, scores, analysis', 10),
('Other', '📋', 'Everything else', 99)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS channels (
    channel_id BIGSERIAL PRIMARY KEY,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    owner_id BIGINT NOT NULL REFERENCES users(user_id),
    title VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    invite_link TEXT,
    description TEXT,
    category_id INTEGER REFERENCES channel_categories(category_id),
    language VARCHAR(50) DEFAULT 'Hindi/English',
    is_verified BOOLEAN DEFAULT FALSE,
    verification_failed_reason TEXT,
    subscriber_count INTEGER DEFAULT 0,
    avg_views_24h INTEGER DEFAULT 0,
    avg_views_7d INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5,2) DEFAULT 0,
    post_frequency_per_day DECIMAL(5,2) DEFAULT 0,
    last_post_at TIMESTAMPTZ,
    stats_updated_at TIMESTAMPTZ,
    activity_score INTEGER DEFAULT 0,
    activity_tier VARCHAR(20) DEFAULT 'low',
    base_price_credits INTEGER DEFAULT 10,
    price_per_hour_credits INTEGER DEFAULT 5,
    min_booking_hours INTEGER DEFAULT 1,
    max_booking_hours INTEGER DEFAULT 168,
    owner_custom_price INTEGER,
    final_price_credits INTEGER DEFAULT 10,
    rules TEXT DEFAULT 'No spam. No adult content. No scams.',
    allowed_content TEXT DEFAULT 'Promotions, products, services',
    forbidden_content TEXT DEFAULT 'Adult content, scams, hate speech',
    requires_approval BOOLEAN DEFAULT FALSE,
    auto_approve BOOLEAN DEFAULT TRUE,
    max_posts_per_advertiser_per_day INTEGER DEFAULT 3,
    is_listed BOOLEAN DEFAULT FALSE,
    is_paused BOOLEAN DEFAULT FALSE,
    is_suspended BOOLEAN DEFAULT FALSE,
    suspension_reason TEXT,
    total_bookings INTEGER DEFAULT 0,
    total_revenue_credits BIGINT DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    listed_at TIMESTAMPTZ,
    last_booking_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_channels_owner ON channels(owner_id);
CREATE INDEX IF NOT EXISTS idx_channels_listed ON channels(is_listed, is_paused, is_suspended);
CREATE INDEX IF NOT EXISTS idx_channels_category ON channels(category_id);
CREATE INDEX IF NOT EXISTS idx_channels_activity ON channels(activity_score DESC);
CREATE INDEX IF NOT EXISTS idx_channels_price ON channels(final_price_credits);
CREATE INDEX IF NOT EXISTS idx_channels_subs ON channels(subscriber_count DESC);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id BIGSERIAL PRIMARY KEY,
    booking_ref VARCHAR(20) UNIQUE NOT NULL,
    advertiser_id BIGINT NOT NULL REFERENCES users(user_id),
    channel_id BIGINT NOT NULL REFERENCES channels(channel_id),
    owner_id BIGINT NOT NULL,
    content_type VARCHAR(20) NOT NULL,
    content_text TEXT,
    media_file_id TEXT,
    caption TEXT,
    inline_buttons_json JSONB,
    duration_hours INTEGER NOT NULL,
    booked_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    posted_at TIMESTAMPTZ,
    scheduled_delete_at TIMESTAMPTZ,
    actual_deleted_at TIMESTAMPTZ,
    telegram_message_id BIGINT,
    price_per_hour_credits INTEGER NOT NULL,
    total_credits_charged INTEGER NOT NULL,
    credits_used INTEGER DEFAULT 0,
    credits_refunded INTEGER DEFAULT 0,
    platform_commission_credits INTEGER DEFAULT 0,
    owner_earnings_credits INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'pending_approval',
    cancelled_at TIMESTAMPTZ,
    cancelled_by VARCHAR(20),
    cancellation_reason TEXT,
    approval_required BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    deleted_early BOOLEAN DEFAULT FALSE,
    deletion_type VARCHAR(30),
    advertiser_rating INTEGER,
    advertiser_review TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookings_advertiser ON bookings(advertiser_id);
CREATE INDEX IF NOT EXISTS idx_bookings_channel ON bookings(channel_id);
CREATE INDEX IF NOT EXISTS idx_bookings_owner ON bookings(owner_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_delete_at ON bookings(scheduled_delete_at) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_bookings_ref ON bookings(booking_ref);

CREATE TABLE IF NOT EXISTS credit_transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    type VARCHAR(50) NOT NULL,
    amount BIGINT NOT NULL,
    balance_before BIGINT NOT NULL,
    balance_after BIGINT NOT NULL,
    booking_id BIGINT REFERENCES bookings(booking_id),
    payout_id BIGINT,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by BIGINT,
    payment_method VARCHAR(50),
    payment_reference VARCHAR(255),
    payment_screenshot_file_id TEXT,
    payment_amount_inr INTEGER,
    payment_verified BOOLEAN DEFAULT FALSE,
    payment_verified_by BIGINT,
    payment_verified_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ct_user ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_ct_type ON credit_transactions(type);
CREATE INDEX IF NOT EXISTS idx_ct_booking ON credit_transactions(booking_id);
CREATE INDEX IF NOT EXISTS idx_ct_created ON credit_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ct_payment ON credit_transactions(payment_verified, type) WHERE type = 'topup_upi' AND payment_verified = FALSE;

CREATE TABLE IF NOT EXISTS payouts (
    payout_id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES users(user_id),
    credits_requested BIGINT NOT NULL,
    inr_amount INTEGER NOT NULL,
    upi_id VARCHAR(255) NOT NULL,
    upi_name VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    processed_by BIGINT,
    processed_at TIMESTAMPTZ,
    transaction_ref VARCHAR(255),
    rejection_reason TEXT,
    requested_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_payouts_owner ON payouts(owner_id);
CREATE INDEX IF NOT EXISTS idx_payouts_status ON payouts(status);

CREATE TABLE IF NOT EXISTS channel_stats_history (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    subscriber_count INTEGER,
    avg_views INTEGER,
    engagement_rate DECIMAL(5,2),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_csh_channel ON channel_stats_history(channel_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS channel_blackouts (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS platform_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string',
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by BIGINT
);

INSERT INTO platform_settings (key, value, value_type, description) VALUES
('platform_commission_percent', '20', 'integer', 'Platform commission on each booking (%)'),
('min_topup_credits', '100', 'integer', 'Minimum credits to top up'),
('max_topup_credits', '100000', 'integer', 'Maximum credits per top-up'),
('min_payout_credits', '500', 'integer', 'Minimum credits for payout request'),
('credits_per_rupee', '1', 'integer', 'How many credits per INR 1'),
('min_booking_hours', '1', 'integer', 'Minimum booking duration (hours)'),
('max_booking_hours', '168', 'integer', 'Maximum booking duration (hours)'),
('base_price_100_subs', '10', 'integer', 'Base credits'),
('price_per_1k_subs', '50', 'integer', 'Additional credits per 1000 subscribers'),
('price_per_100_views', '10', 'integer', 'Additional credits per 100 avg views'),
('activity_multiplier_high', '1.5', 'float', 'Multiplier for high activity channels'),
('activity_multiplier_medium', '1.0', 'float', 'Multiplier for medium activity'),
('activity_multiplier_low', '0.6', 'float', 'Multiplier for low activity channels'),
('high_activity_threshold', '70', 'integer', 'Activity score threshold for HIGH tier'),
('medium_activity_threshold', '40', 'integer', 'Activity score threshold for MEDIUM tier'),
('deletion_check_interval_seconds', '60', 'integer', 'How often to check for expired posts'),
('stats_refresh_hours', '6', 'integer', 'How often to refresh channel stats'),
('max_channels_per_owner', '10', 'integer', 'Max channels one owner can list'),
('max_active_bookings_per_advertiser', '20', 'integer', 'Max simultaneous active bookings'),
('referral_bonus_credits', '50', 'integer', 'Credits for referring a new user'),
('new_user_bonus_credits', '25', 'integer', 'Bonus credits for new registrations'),
('marketplace_enabled', 'true', 'boolean', 'Is the marketplace accepting new bookings'),
('maintenance_mode', 'false', 'boolean', 'Maintenance mode'),
('maintenance_message', 'Bot is under maintenance. Back soon!', 'string', 'Message shown during maintenance'),
('watermark_enabled', 'true', 'boolean', 'Append promo footer to ads')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    type VARCHAR(50) NOT NULL,
    booking_id BIGINT,
    message_preview TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_type ON notifications(type);

CREATE TABLE IF NOT EXISTS reviews (
    review_id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT UNIQUE NOT NULL REFERENCES bookings(booking_id),
    channel_id BIGINT NOT NULL REFERENCES channels(channel_id),
    advertiser_id BIGINT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_visible BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_reviews_channel ON reviews(channel_id);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    booking_ref VARCHAR(20),
    status VARCHAR(20) DEFAULT 'open',
    priority VARCHAR(10) DEFAULT 'normal',
    assigned_to BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON support_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status);

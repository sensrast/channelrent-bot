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
    notify_new_booking BOOLEAN DEFAULT TRUE,
    notify_post_live BOOLEAN DEFAULT TRUE,
    notify_post_deleted BOOLEAN DEFAULT TRUE,
    notify_payment_received BOOLEAN DEFAULT TRUE,
    notify_credits_low BOOLEAN DEFAULT TRUE,
    has_blocked_bot BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_users_owner ON users(is_owner);
CREATE INDEX IF NOT EXISTS idx_users_advertiser ON users(is_advertiser);

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
('Technology', '💻', 'Tech', 1),
('Crypto & Finance', '₿', 'Crypto', 2),
('Education', '📚', 'Edu', 3),
('Entertainment', '🎬', 'Fun', 4),
('News', '📰', 'News', 5),
('Gaming', '🎮', 'Games', 6),
('Health & Fitness', '💪', 'Health', 7),
('Business', '💼', 'Biz', 8),
('Lifestyle', '✨', 'Lifestyle', 9),
('Sports', '⚽', 'Sports', 10),
('Other', '📋', 'Other', 99)
ON CONFLICT DO NOTHING;

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
    rules TEXT,
    allowed_content TEXT,
    forbidden_content TEXT,
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
CREATE INDEX IF NOT EXISTS idx_channels_listed ON channels(is_listed);

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
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);

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

CREATE TABLE IF NOT EXISTS platform_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string',
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by BIGINT
);

INSERT INTO platform_settings (key, value, value_type, description) VALUES
('platform_commission_percent', '20', 'integer', 'Platform commission %'),
('credits_per_rupee', '1', 'integer', 'Credits per INR 1'),
('marketplace_enabled', 'true', 'boolean', 'Marketplace open'),
('maintenance_mode', 'false', 'boolean', 'Maintenance mode')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    type VARCHAR(50) NOT NULL,
    booking_id BIGINT,
    message_preview TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered BOOLEAN DEFAULT TRUE
);

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

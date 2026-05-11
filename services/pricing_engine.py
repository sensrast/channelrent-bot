import math
import config

def compute_activity(subscribers, avg_views, engagement_rate=None):
    s = max(int(subscribers or 0), 0)
    v = max(int(avg_views or 0), 0)
    if engagement_rate is None:
        engagement_rate = (v / s * 100) if s > 0 else 0
    view_score = min(v / max(s * 0.8, 1), 1) * 40
    sub_score = min(s / 10000, 1) * 30
    eng_score = min(engagement_rate / 80, 1) * 30
    score = round(view_score + sub_score + eng_score)
    if score >= 70: tier = "high"
    elif score >= 40: tier = "medium"
    else: tier = "low"
    return score, tier, round(engagement_rate, 2)

def activity_multiplier(tier):
    return {
        "high": config.ACTIVITY_MULTIPLIER_HIGH,
        "medium": config.ACTIVITY_MULTIPLIER_MEDIUM,
        "low": config.ACTIVITY_MULTIPLIER_LOW,
    }.get(tier, config.ACTIVITY_MULTIPLIER_MEDIUM)

def compute_price_per_hour(subscribers, avg_views, tier=None):
    s = max(int(subscribers or 0), 0)
    v = max(int(avg_views or 0), 0)
    base = config.BASE_PRICE_PER_POST_CREDITS
    sub_bonus = (s / 1000.0) * config.PRICE_PER_1K_SUBSCRIBERS
    view_bonus = (v / 100.0) * config.PRICE_PER_100_VIEWS
    raw = base + sub_bonus + view_bonus
    if tier is None:
        _, tier, _ = compute_activity(s, v)
    final = raw * activity_multiplier(tier)
    return max(config.MIN_LISTING_PRICE, min(int(round(final)), config.MAX_LISTING_PRICE))

def clamp_owner_price(suggested, custom):
    if custom is None: return suggested
    lo = max(config.MIN_LISTING_PRICE, int(suggested * 0.5))
    hi = min(config.MAX_LISTING_PRICE, int(suggested * 1.5))
    return max(lo, min(int(custom), hi))

def commission_split(total_credits):
    pct = config.PLATFORM_COMMISSION_PERCENT
    commission = int(round(total_credits * pct / 100.0))
    owner = total_credits - commission
    return commission, owner

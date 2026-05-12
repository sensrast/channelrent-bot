from database.pool import db

async def platform_overview():
    total_users = await db.fetchval("SELECT COUNT(*) FROM users") or 0
    listed = await db.fetchval("SELECT COUNT(*) FROM channels WHERE is_listed=TRUE") or 0
    active = await db.fetchval("SELECT COUNT(*) FROM bookings WHERE status='active'") or 0
    credits = await db.fetchval("SELECT COALESCE(SUM(credits_balance),0) FROM users") or 0
    rev_today = await db.fetchval("SELECT COALESCE(SUM(platform_commission_credits),0) FROM bookings WHERE status IN ('completed','completed_early') AND DATE(actual_deleted_at)=CURRENT_DATE") or 0
    rev_month = await db.fetchval("SELECT COALESCE(SUM(platform_commission_credits),0) FROM bookings WHERE status IN ('completed','completed_early') AND actual_deleted_at >= date_trunc('month', NOW())") or 0
    pending_payouts = await db.fetchval("SELECT COUNT(*) FROM payouts WHERE status='pending'") or 0
    pending_payout_inr = await db.fetchval("SELECT COALESCE(SUM(inr_amount),0) FROM payouts WHERE status='pending'") or 0
    pending_topups = await db.fetchval("SELECT COUNT(*) FROM credit_transactions WHERE type='topup_upi' AND payment_verified=FALSE") or 0
    pending_topup_inr = await db.fetchval("SELECT COALESCE(SUM(payment_amount_inr),0) FROM credit_transactions WHERE type='topup_upi' AND payment_verified=FALSE") or 0
    return dict(total_users=total_users, listed=listed, active=active, credits=credits,
                rev_today=rev_today, rev_month=rev_month,
                pending_payouts=pending_payouts, pending_payout_inr=pending_payout_inr,
                pending_topups=pending_topups, pending_topup_inr=pending_topup_inr)

async def top_channels(limit=10):
    return await db.fetch("SELECT channel_id, title, username, invite_link, telegram_chat_id, total_bookings FROM channels ORDER BY total_bookings DESC LIMIT $1", limit)

async def bookings_last_7_days():
    return await db.fetch("""
        SELECT DATE(booked_at) as day, COUNT(*) as cnt FROM bookings
        WHERE booked_at >= NOW() - INTERVAL '7 days'
        GROUP BY day ORDER BY day
    """)

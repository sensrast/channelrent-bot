from database.pool import db
from database.queries.credits import adjust_credits
from database.queries.payouts import create_payout, mark_paid, mark_rejected, get_payout

async def request_payout(owner_id, credits_amount, inr_amount, upi_id, upi_name):
    async with db.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT earnings_pending FROM users WHERE user_id=$1 FOR UPDATE", owner_id)
            if not row or row["earnings_pending"] < credits_amount:
                raise ValueError("Insufficient pending earnings")
            await conn.execute("UPDATE users SET earnings_pending=earnings_pending-$2 WHERE user_id=$1", owner_id, credits_amount)
            payout_id = await conn.fetchval("""INSERT INTO payouts (owner_id,credits_requested,inr_amount,upi_id,upi_name) VALUES ($1,$2,$3,$4,$5) RETURNING payout_id""", owner_id, credits_amount, inr_amount, upi_id, upi_name)
            return payout_id

async def complete_payout(payout_id, admin_id, ref):
    p = await get_payout(payout_id)
    if not p or p["status"] != "pending": return None
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE users SET earnings_paid=earnings_paid+$2 WHERE user_id=$1", p["owner_id"], p["credits_requested"])
            await conn.execute("UPDATE payouts SET status='completed', processed_by=$2, processed_at=NOW(), transaction_ref=$3 WHERE payout_id=$1", payout_id, admin_id, ref)
    return p

async def reject_payout(payout_id, admin_id, reason):
    p = await get_payout(payout_id)
    if not p or p["status"] != "pending": return None
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE users SET earnings_pending=earnings_pending+$2 WHERE user_id=$1", p["owner_id"], p["credits_requested"])
            await conn.execute("UPDATE payouts SET status='rejected', processed_by=$2, processed_at=NOW(), rejection_reason=$3 WHERE payout_id=$1", payout_id, admin_id, reason)
    return p

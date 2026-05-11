from database.pool import db

async def create_payout(owner_id, credits, inr, upi_id, upi_name):
    return await db.fetchval("""
        INSERT INTO payouts (owner_id, credits_requested, inr_amount, upi_id, upi_name)
        VALUES ($1,$2,$3,$4,$5) RETURNING payout_id
    """, owner_id, credits, inr, upi_id, upi_name)

async def list_pending():
    return await db.fetch("SELECT * FROM payouts WHERE status='pending' ORDER BY requested_at ASC")

async def get_payout(payout_id):
    return await db.fetchrow("SELECT * FROM payouts WHERE payout_id=$1", payout_id)

async def mark_paid(payout_id, admin_id, ref):
    await db.execute("""UPDATE payouts SET status='completed', processed_by=$2, processed_at=NOW(), transaction_ref=$3 WHERE payout_id=$1""", payout_id, admin_id, ref)

async def mark_rejected(payout_id, admin_id, reason):
    await db.execute("""UPDATE payouts SET status='rejected', processed_by=$2, processed_at=NOW(), rejection_reason=$3 WHERE payout_id=$1""", payout_id, admin_id, reason)

async def list_owner_payouts(owner_id, limit=20):
    return await db.fetch("SELECT * FROM payouts WHERE owner_id=$1 ORDER BY requested_at DESC LIMIT $2", owner_id, limit)

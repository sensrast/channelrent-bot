from database.pool import db

async def adjust_credits(conn, user_id, delta, tx_type, description=None, booking_id=None, created_by=None, payment_method=None, payment_reference=None, payment_screenshot_file_id=None, payment_amount_inr=None, payment_verified=False):
    from decimal import Decimal
    row = await conn.fetchrow("SELECT credits_balance FROM users WHERE user_id=$1 FOR UPDATE", user_id)
    if not row:
        raise ValueError("user not found")
    bal = Decimal(str(row["credits_balance"] or 0))
    delta = Decimal(str(delta))
    new_bal = (bal + delta).quantize(Decimal("0.01"))
    if new_bal < 0:
        raise ValueError("insufficient credits")
    await conn.execute("UPDATE users SET credits_balance=$2 WHERE user_id=$1", user_id, new_bal)
    if delta > 0 and tx_type in ("topup_manual","topup_upi","referral_bonus","platform_bonus"):
        await conn.execute("UPDATE users SET credits_total_purchased=credits_total_purchased+$2 WHERE user_id=$1", user_id, delta)
    if delta < 0 and tx_type == "booking_charge":
        await conn.execute("UPDATE users SET credits_total_spent=credits_total_spent+$2 WHERE user_id=$1", user_id, -delta)
    if delta > 0 and tx_type in ("booking_refund","booking_cancelled"):
        await conn.execute("UPDATE users SET credits_total_refunded=credits_total_refunded+$2 WHERE user_id=$1", user_id, delta)
    tx_id = await conn.fetchval("""
        INSERT INTO credit_transactions (user_id, type, amount, balance_before, balance_after, booking_id, description, created_by, payment_method, payment_reference, payment_screenshot_file_id, payment_amount_inr, payment_verified)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        RETURNING transaction_id
    """, user_id, tx_type, delta, bal, new_bal, booking_id, description, created_by, payment_method, payment_reference, payment_screenshot_file_id, payment_amount_inr, payment_verified)
    return tx_id, new_bal

async def add_pending_earning(conn, user_id, amount):
    await conn.execute("UPDATE users SET earnings_pending=earnings_pending+$2 WHERE user_id=$1", user_id, amount)

async def get_balance(user_id):
    return await db.fetchval("SELECT credits_balance FROM users WHERE user_id=$1", user_id) or 0

async def list_transactions(user_id, limit=20):
    return await db.fetch("SELECT * FROM credit_transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2", user_id, limit)

async def list_pending_topups():
    return await db.fetch("""
        SELECT * FROM credit_transactions
        WHERE type='topup_upi' AND payment_verified=FALSE
        ORDER BY created_at ASC
    """)

async def get_transaction(tx_id):
    return await db.fetchrow("SELECT * FROM credit_transactions WHERE transaction_id=$1", tx_id)

async def mark_payment_verified(tx_id, admin_id):
    await db.execute("""
        UPDATE credit_transactions
        SET payment_verified=TRUE, payment_verified_by=$2, payment_verified_at=NOW()
        WHERE transaction_id=$1
    """, tx_id, admin_id)

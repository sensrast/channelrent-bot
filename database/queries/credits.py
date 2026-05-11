from database.pool import get_pool


class InsufficientCreditsError(Exception):
    pass


async def add_credits(user_id, amount, tx_type, description='', booking_id=None, created_by=None):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow('SELECT credits_balance FROM users WHERE user_id=$1 FOR UPDATE', user_id)
            balance_before = row['credits_balance'] if row else 0
            balance_after = balance_before + amount
            await conn.execute('UPDATE users SET credits_balance=$1 WHERE user_id=$2', balance_after, user_id)
            await conn.execute('INSERT INTO credit_transactions (user_id, type, amount, balance_before, balance_after, booking_id, description, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)', user_id, tx_type, amount, balance_before, balance_after, booking_id, description, created_by)
            return balance_after


async def deduct_credits(user_id, amount, tx_type, description='', booking_id=None):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow('SELECT credits_balance FROM users WHERE user_id=$1 FOR UPDATE', user_id)
            balance_before = row['credits_balance'] if row else 0
            if balance_before < amount:
                raise InsufficientCreditsError(f'Need {amount}, has {balance_before}')
            balance_after = balance_before - amount
            await conn.execute('UPDATE users SET credits_balance=$1, credits_total_spent=credits_total_spent+$2 WHERE user_id=$3', balance_after, amount, user_id)
            await conn.execute('INSERT INTO credit_transactions (user_id, type, amount, balance_before, balance_after, booking_id, description) VALUES ($1,$2,$3,$4,$5,$6,$7)', user_id, tx_type, -amount, balance_before, balance_after, booking_id, description)
            return balance_after

from database.pool import db

async def upsert_user(user_id, username, first_name, last_name, language_code="en"):
    row = await db.fetchrow("SELECT user_id FROM users WHERE user_id=$1", user_id)
    is_new = row is None
    if is_new:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, language_code, referral_code)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, username, first_name, last_name, language_code, f"ref{user_id}")
    else:
        await db.execute("""
            UPDATE users SET username=$2, first_name=$3, last_name=$4, last_active=NOW()
            WHERE user_id=$1
        """, user_id, username, first_name, last_name)
    return is_new

async def get_user(user_id):
    return await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def set_referrer(user_id, referrer_id):
    await db.execute("UPDATE users SET referred_by=$2 WHERE user_id=$1 AND referred_by IS NULL", user_id, referrer_id)
    await db.execute("UPDATE users SET referral_count=referral_count+1 WHERE user_id=$1", referrer_id)

async def set_banned(user_id, banned: bool, reason=None):
    await db.execute("UPDATE users SET is_banned=$2, ban_reason=$3 WHERE user_id=$1", user_id, banned, reason)

async def mark_blocked_bot(user_id):
    await db.execute("UPDATE users SET has_blocked_bot=TRUE WHERE user_id=$1", user_id)

async def set_upi(user_id, upi_id, upi_name):
    await db.execute("UPDATE users SET upi_id=$2 WHERE user_id=$1", user_id, upi_id)

async def search_users(query, limit=20):
    if query.isdigit():
        return await db.fetch("SELECT * FROM users WHERE user_id=$1", int(query))
    q = f"%{query.lower().lstrip('@')}%"
    return await db.fetch("""
        SELECT * FROM users 
        WHERE LOWER(username) LIKE $1 OR LOWER(first_name) LIKE $1
        LIMIT $2
    """, q, limit)

async def count_users():
    return await db.fetchval("SELECT COUNT(*) FROM users")

async def all_user_ids(only_active=True):
    if only_active:
        return [r["user_id"] for r in await db.fetch("SELECT user_id FROM users WHERE is_banned=FALSE AND has_blocked_bot=FALSE")]
    return [r["user_id"] for r in await db.fetch("SELECT user_id FROM users")]

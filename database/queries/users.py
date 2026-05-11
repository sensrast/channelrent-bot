from database.pool import fetchrow, execute, fetchval


async def upsert_user(user_id, username, first_name, last_name):
    row = await fetchrow("""
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO UPDATE
        SET username=EXCLUDED.username, first_name=EXCLUDED.first_name,
            last_name=EXCLUDED.last_name, last_active=NOW()
        RETURNING *
    """, user_id, username, first_name, last_name)
    return dict(row) if row else {}


async def get_user(user_id):
    row = await fetchrow('SELECT * FROM users WHERE user_id=$1', user_id)
    return dict(row) if row else None


async def set_banned(user_id, banned, reason=None):
    await execute('UPDATE users SET is_banned=$1, ban_reason=$2 WHERE user_id=$3', banned, reason, user_id)


async def count_users():
    return await fetchval('SELECT COUNT(*) FROM users') or 0

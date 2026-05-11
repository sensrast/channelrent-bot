from database.pool import db

async def get_channel(channel_id):
    return await db.fetchrow("SELECT c.*, cat.name as category_name, cat.emoji as category_emoji FROM channels c LEFT JOIN channel_categories cat ON cat.category_id=c.category_id WHERE c.channel_id=$1", channel_id)

async def get_channel_by_chat(chat_id):
    return await db.fetchrow("SELECT * FROM channels WHERE telegram_chat_id=$1", chat_id)

async def list_owner_channels(owner_id):
    return await db.fetch("SELECT * FROM channels WHERE owner_id=$1 ORDER BY added_at DESC", owner_id)

async def count_owner_channels(owner_id):
    return await db.fetchval("SELECT COUNT(*) FROM channels WHERE owner_id=$1", owner_id) or 0

async def create_channel(**kw):
    keys = list(kw.keys())
    placeholders = ",".join(f"${i+1}" for i in range(len(keys)))
    cols = ",".join(keys)
    q = f"INSERT INTO channels ({cols}) VALUES ({placeholders}) RETURNING channel_id"
    return await db.fetchval(q, *[kw[k] for k in keys])

async def update_channel(channel_id, **kw):
    if not kw: return
    sets = ",".join(f"{k}=${i+2}" for i,k in enumerate(kw.keys()))
    q = f"UPDATE channels SET {sets} WHERE channel_id=$1"
    await db.execute(q, channel_id, *kw.values())

async def list_marketplace(category_id=None, activity_tier=None, budget_max=None, min_subs=None, sort="rating", offset=0, limit=5):
    where = ["is_listed=TRUE","is_paused=FALSE","is_suspended=FALSE","is_verified=TRUE"]
    params = []
    if category_id:
        params.append(category_id); where.append(f"category_id=${len(params)}")
    if activity_tier:
        params.append(activity_tier); where.append(f"activity_tier=${len(params)}")
    if budget_max:
        params.append(budget_max); where.append(f"final_price_credits<=${len(params)}")
    if min_subs:
        params.append(min_subs); where.append(f"subscriber_count>=${len(params)}")
    order = {
        "rating":"rating DESC, rating_count DESC",
        "price_asc":"final_price_credits ASC",
        "price_desc":"final_price_credits DESC",
        "subs":"subscriber_count DESC",
        "activity":"activity_score DESC",
    }.get(sort, "rating DESC")
    params.extend([limit, offset])
    q = f"""SELECT c.*, cat.name as category_name, cat.emoji as category_emoji
        FROM channels c LEFT JOIN channel_categories cat ON cat.category_id=c.category_id
        WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ${len(params)-1} OFFSET ${len(params)}"""
    return await db.fetch(q, *params)

async def count_marketplace(category_id=None, activity_tier=None, budget_max=None, min_subs=None):
    where = ["is_listed=TRUE","is_paused=FALSE","is_suspended=FALSE","is_verified=TRUE"]
    params = []
    if category_id:
        params.append(category_id); where.append(f"category_id=${len(params)}")
    if activity_tier:
        params.append(activity_tier); where.append(f"activity_tier=${len(params)}")
    if budget_max:
        params.append(budget_max); where.append(f"final_price_credits<=${len(params)}")
    if min_subs:
        params.append(min_subs); where.append(f"subscriber_count>=${len(params)}")
    q = f"SELECT COUNT(*) FROM channels WHERE {' AND '.join(where)}"
    return await db.fetchval(q, *params) or 0

async def list_all_categories():
    return await db.fetch("SELECT * FROM channel_categories WHERE is_active=TRUE ORDER BY sort_order")

async def list_all_listed():
    return await db.fetch("SELECT * FROM channels WHERE is_listed=TRUE AND is_suspended=FALSE")

async def list_all_verified():
    return await db.fetch("SELECT * FROM channels WHERE is_verified=TRUE")

async def count_channels():
    return await db.fetchval("SELECT COUNT(*) FROM channels WHERE is_listed=TRUE") or 0

async def update_rating(channel_id):
    await db.execute("""
        UPDATE channels SET 
          rating=(SELECT COALESCE(AVG(rating),0) FROM reviews WHERE channel_id=$1 AND is_visible=TRUE),
          rating_count=(SELECT COUNT(*) FROM reviews WHERE channel_id=$1 AND is_visible=TRUE)
        WHERE channel_id=$1
    """, channel_id)

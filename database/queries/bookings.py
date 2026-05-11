from database.pool import db
from datetime import date

async def generate_booking_ref():
    today = date.today().strftime("%Y%m%d")
    count = await db.fetchval("SELECT COUNT(*) FROM bookings WHERE booking_ref LIKE $1", f"BK-{today}-%") or 0
    return f"BK-{today}-{count+1:04d}"

async def create_booking(conn, **kw):
    keys = list(kw.keys())
    placeholders = ",".join(f"${i+1}" for i in range(len(keys)))
    cols = ",".join(keys)
    q = f"INSERT INTO bookings ({cols}) VALUES ({placeholders}) RETURNING booking_id"
    return await conn.fetchval(q, *[kw[k] for k in keys])

async def get_booking(booking_id):
    return await db.fetchrow("""SELECT b.*, c.title as channel_title, c.telegram_chat_id, c.username as channel_username
        FROM bookings b JOIN channels c ON c.channel_id=b.channel_id WHERE booking_id=$1""", booking_id)

async def get_booking_by_ref(ref):
    return await db.fetchrow("SELECT * FROM bookings WHERE booking_ref=$1", ref)

async def list_advertiser_bookings(advertiser_id, status_in=None, limit=50, offset=0):
    if status_in:
        return await db.fetch("""SELECT b.*, c.title as channel_title FROM bookings b
            JOIN channels c ON c.channel_id=b.channel_id
            WHERE advertiser_id=$1 AND status=ANY($2::text[])
            ORDER BY booked_at DESC LIMIT $3 OFFSET $4""", advertiser_id, status_in, limit, offset)
    return await db.fetch("""SELECT b.*, c.title as channel_title FROM bookings b
        JOIN channels c ON c.channel_id=b.channel_id
        WHERE advertiser_id=$1 ORDER BY booked_at DESC LIMIT $2 OFFSET $3""", advertiser_id, limit, offset)

async def list_owner_bookings(owner_id, status_in=None, limit=50, offset=0):
    if status_in:
        return await db.fetch("""SELECT b.*, c.title as channel_title FROM bookings b
            JOIN channels c ON c.channel_id=b.channel_id
            WHERE b.owner_id=$1 AND status=ANY($2::text[])
            ORDER BY booked_at DESC LIMIT $3 OFFSET $4""", owner_id, status_in, limit, offset)
    return await db.fetch("""SELECT b.*, c.title as channel_title FROM bookings b
        JOIN channels c ON c.channel_id=b.channel_id
        WHERE b.owner_id=$1 ORDER BY booked_at DESC LIMIT $2 OFFSET $3""", owner_id, limit, offset)

async def update_booking(booking_id, **kw):
    if not kw: return
    sets = ",".join(f"{k}=${i+2}" for i,k in enumerate(kw.keys()))
    q = f"UPDATE bookings SET {sets} WHERE booking_id=$1"
    await db.execute(q, booking_id, *kw.values())

async def list_active_expired():
    return await db.fetch("SELECT * FROM bookings WHERE status='active' AND scheduled_delete_at <= NOW()")

async def list_active_bookings():
    return await db.fetch("SELECT * FROM bookings WHERE status='active'")

async def count_active_bookings():
    return await db.fetchval("SELECT COUNT(*) FROM bookings WHERE status='active'") or 0

async def count_advertiser_active(advertiser_id):
    return await db.fetchval("SELECT COUNT(*) FROM bookings WHERE advertiser_id=$1 AND status IN ('active','approved','pending_approval')", advertiser_id) or 0

async def list_old_pending_approval(hours=4):
    return await db.fetch(f"SELECT * FROM bookings WHERE status='pending_approval' AND booked_at <= NOW() - INTERVAL '{int(hours)} hours'")

async def revenue_today():
    return await db.fetchval("SELECT COALESCE(SUM(platform_commission_credits),0) FROM bookings WHERE status IN ('completed','completed_early') AND DATE(actual_deleted_at)=CURRENT_DATE") or 0

async def revenue_month():
    return await db.fetchval("SELECT COALESCE(SUM(platform_commission_credits),0) FROM bookings WHERE status IN ('completed','completed_early') AND actual_deleted_at >= date_trunc('month', NOW())") or 0

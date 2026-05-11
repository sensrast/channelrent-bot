from datetime import datetime, timezone
from database.pool import db
from database.queries.credits import adjust_credits, add_pending_earning
from database.queries.bookings import update_booking
from services.pricing_engine import commission_split

def _now():
    return datetime.now(timezone.utc)

async def settle_booking(booking_id, deletion_type, deleted_at=None):
    """
    deletion_type: 'scheduled' | 'advertiser_requested' | 'owner_deleted' | 'admin_deleted' | 'message_lost'
    Returns (refund_to_advertiser, owner_earning, platform_commission).
    """
    deleted_at = deleted_at or _now()
    async with db.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM bookings WHERE booking_id=$1 FOR UPDATE", booking_id)
            if not row: return 0,0,0
            if row["status"] in ("completed","completed_early","cancelled","rejected"):
                return 0,0,0
            total = row["total_credits_charged"]
            posted = row["posted_at"]
            duration_h = row["duration_hours"]
            price_per_h = row["price_per_hour_credits"]
            if posted is None:
                refund = total
                owner_earn = 0
                commission = 0
                final_status = "cancelled"
            else:
                if posted.tzinfo is None: posted = posted.replace(tzinfo=timezone.utc)
                from decimal import Decimal, ROUND_HALF_UP
                elapsed_seconds = max(0.0, (deleted_at - posted).total_seconds())
                max_seconds = float(duration_h) * 3600.0
                elapsed_seconds = min(elapsed_seconds, max_seconds)
                if deletion_type in ("owner_deleted","message_lost","admin_deleted"):
                    refund = total
                    owner_earn = 0
                    commission = 0
                    final_status = "completed_early"
                else:
                    pph = Decimal(str(price_per_h))
                    credits_used = (pph * Decimal(elapsed_seconds) / Decimal(3600)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                    if credits_used > Decimal(str(total)): credits_used = Decimal(str(total))
                    refund = (Decimal(str(total)) - credits_used).quantize(Decimal("0.0001"))
                    commission, owner_earn = commission_split(credits_used)
                    final_status = "completed" if deletion_type == "scheduled" else "completed_early"
            await conn.execute("""UPDATE bookings SET
                status=$2, actual_deleted_at=$3, deletion_type=$4, deleted_early=$5,
                credits_used=$6, credits_refunded=$7,
                platform_commission_credits=$8, owner_earnings_credits=$9
                WHERE booking_id=$1""",
                booking_id, final_status, deleted_at, deletion_type, final_status=="completed_early",
                total-refund, refund, commission, owner_earn)
            if refund > 0:
                await adjust_credits(conn, row["advertiser_id"], refund,
                    "booking_refund" if final_status=="completed_early" else "booking_cancelled",
                    description=f"Refund for booking #{booking_id}", booking_id=booking_id)
            if owner_earn > 0:
                await add_pending_earning(conn, row["owner_id"], owner_earn)
                await conn.execute("INSERT INTO credit_transactions (user_id, type, amount, balance_before, balance_after, booking_id, description) VALUES ($1,'owner_earning',$2,0,0,$3,$4)",
                    row["owner_id"], owner_earn, booking_id, f"Earnings from booking #{booking_id}")
            if deletion_type == "owner_deleted":
                await conn.execute("UPDATE users SET reliability_strikes=reliability_strikes+1 WHERE user_id=$1", row["owner_id"])
            await conn.execute("UPDATE channels SET total_bookings=total_bookings+1, total_revenue_credits=total_revenue_credits+$2 WHERE channel_id=$1", row["channel_id"], owner_earn)
            return refund, owner_earn, commission

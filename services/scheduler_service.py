import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import config
from services.deletion_service import process_expired, check_message_existence
from services.notification_service import notify
from database.queries.bookings import list_old_pending_approval
from database.queries.channels import list_all_verified, update_channel
from database.queries.users import all_user_ids
from database.pool import db

log = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None

async def _pending_reminder(bot):
    rows = await list_old_pending_approval(4)
    seen = set()
    for b in rows:
        if b["owner_id"] in seen: continue
        seen.add(b["owner_id"])
        await notify(bot, b["owner_id"], "pending_reminder",
            f"⏰ You have pending booking requests. Please review them.", booking_id=b["booking_id"])

async def _low_credits_alert(bot):
    rows = await db.fetch("""SELECT user_id, credits_balance FROM users
        WHERE notify_credits_low=TRUE AND credits_balance < 100 AND has_blocked_bot=FALSE
        AND user_id IN (SELECT advertiser_id FROM bookings WHERE booked_at >= NOW() - INTERVAL '7 days')""")
    for r in rows[:200]:
        await notify(bot, r["user_id"], "low_credits",
            f"💡 Low credits! Balance: {r['credits_balance']} credits. Top up to keep booking.")

def start(bot):
    global scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(process_expired, IntervalTrigger(seconds=config.DELETION_CHECK_INTERVAL_SECONDS), args=[bot], id="deletion", max_instances=1)
    scheduler.add_job(check_message_existence, IntervalTrigger(minutes=1), args=[bot], id="exists", max_instances=1)
    scheduler.add_job(_pending_reminder, IntervalTrigger(hours=2), args=[bot], id="pending_reminder", max_instances=1)
    scheduler.add_job(_low_credits_alert, IntervalTrigger(hours=6), args=[bot], id="low_credits", max_instances=1)

    scheduler.start()
    log.info("Scheduler started")
    return scheduler

def stop():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None

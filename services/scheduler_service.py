import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import config
from services.deletion_service import process_expired, check_message_existence
from services.notification_service import notify
from database.queries.bookings import list_old_pending_approval
from database.queries.channels import list_all_verified, update_channel, list_all_listed
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


async def _cleanup_inactive_channels(bot):
    rows = await db.fetch("SELECT channel_id, owner_id, title, telegram_chat_id FROM channels WHERE is_active=TRUE AND is_listed=TRUE")
    for r in rows:
        try:
            last = None
            try:
                msgs = await bot.get_chat(r["telegram_chat_id"])
                pinned = getattr(msgs, "pinned_message", None)
                if pinned and getattr(pinned, "date", None):
                    last = pinned.date
            except Exception:
                pass
            cur = await db.fetchrow("SELECT last_message_at FROM channels WHERE channel_id=$1", r["channel_id"])
            db_last = cur["last_message_at"] if cur else None
            from datetime import datetime, timezone, timedelta
            threshold = datetime.now(timezone.utc) - timedelta(days=30)
            effective = max([d for d in [last, db_last] if d is not None], default=None)
            if effective is None or effective < threshold:
                await update_channel(r["channel_id"], is_active=False, is_listed=False, is_paused=True)
                try:
                    await notify(bot, r["owner_id"], "channel_removed",
                        f"⚠️ Channel <b>{r['title']}</b> was auto-removed: no posts in the last 30 days.")
                except Exception:
                    pass
        except Exception as e:
            log.debug("inactive cleanup err %s: %s", r["channel_id"], e)

def start(bot):
    global scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(process_expired, IntervalTrigger(seconds=min(30, config.DELETION_CHECK_INTERVAL_SECONDS)), args=[bot], id="deletion", max_instances=1)
    scheduler.add_job(check_message_existence, IntervalTrigger(seconds=10), args=[bot], id="exists", max_instances=1)
    scheduler.add_job(_pending_reminder, IntervalTrigger(hours=2), args=[bot], id="pending_reminder", max_instances=1)
    scheduler.add_job(_low_credits_alert, IntervalTrigger(hours=6), args=[bot], id="low_credits", max_instances=1)
    scheduler.add_job(_cleanup_inactive_channels, IntervalTrigger(hours=12), args=[bot], id="inactive_cleanup", max_instances=1)

    scheduler.start()
    log.info("Scheduler started")
    return scheduler

def stop():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None

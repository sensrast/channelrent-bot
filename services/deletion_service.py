import asyncio
import logging
from telegram import Bot
import config
from database.queries.bookings import list_active_expired, list_active_bookings
from database.queries.channels import get_channel
from services.broadcast_service import delete_from_channel, message_exists
from services.refund_service import settle_booking
from services.notification_service import notify

log = logging.getLogger(__name__)

EXISTENCE_CHECK_CONCURRENCY = 8

def _probe_target():
    return config.SUPERADMIN_IDS[0] if config.SUPERADMIN_IDS else None

async def process_expired(bot: Bot):
    rows = await list_active_expired()
    for b in rows:
        try:
            ch = await get_channel(b["channel_id"])
            if not ch:
                await settle_booking(b["booking_id"], "message_lost")
                continue
            ok = await delete_from_channel(bot, ch["telegram_chat_id"], b["telegram_message_id"])
            dtype = "scheduled" if ok else "message_lost"
            refund, owner_earn, commission = await settle_booking(b["booking_id"], dtype)
            await notify(bot, b["advertiser_id"], "post_completed",
                f"✅ <b>Ad completed</b>\nBooking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n💰 Credits used: {b['total_credits_charged']-refund}\n" + (f"🔁 Refund: {refund} credits" if refund>0 else ""),
                booking_id=b["booking_id"])
            await notify(bot, b["owner_id"], "post_completed",
                f"✅ <b>Booking completed</b>\nBooking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n💰 You earned: {owner_earn} credits",
                booking_id=b["booking_id"])
        except Exception as e:
            log.exception("expired processing failed for booking %s: %s", b.get("booking_id"), e)


async def _check_one_booking(bot: Bot, b: dict, target):
    try:
        ch = await get_channel(b["channel_id"])
        if not ch or not b["telegram_message_id"]:
            return False
        present = await message_exists(
            bot, ch["telegram_chat_id"], b["telegram_message_id"],
            probe_chat_id=target,
            inline_buttons_json=b.get("inline_buttons_json"),
        )
        if present:
            return False
        log.info("Owner-deleted post detected: booking_id=%s ref=%s channel=%s",
                 b.get("booking_id"), b.get("booking_ref"), ch.get("title"))
        refund, owner_earn, _ = await settle_booking(b["booking_id"], "owner_deleted")
        try:
            await notify(bot, b["advertiser_id"], "owner_deleted_post",
                f"⚠️ <b>Your ad was removed early by the channel owner</b>\n"
                f"Booking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n"
                f"💰 Full refund: {refund} credits returned to your wallet.",
                booking_id=b["booking_id"])
        except Exception as e:
            log.warning("notify advertiser failed for %s: %s", b.get("booking_id"), e)
        try:
            await notify(bot, b["owner_id"], "owner_deleted_post",
                f"ℹ️ Booking <code>{b['booking_ref']}</code> on {ch['title']} was no longer present. "
                f"The advertiser was fully refunded. Repeated early deletions affect your reliability score.",
                booking_id=b["booking_id"])
        except Exception as e:
            log.warning("notify owner failed for %s: %s", b.get("booking_id"), e)
        return True
    except Exception as e:
        log.debug("existence check failed for %s: %s", b.get("booking_id"), e)
        return False


async def check_message_existence(bot: Bot):
    target = _probe_target()
    rows = await list_active_bookings()
    if not rows:
        return 0
    sem = asyncio.Semaphore(EXISTENCE_CHECK_CONCURRENCY)

    async def _bounded(b):
        async with sem:
            return await _check_one_booking(bot, b, target)

    results = await asyncio.gather(*[_bounded(b) for b in rows], return_exceptions=True)
    detected = sum(1 for r in results if r is True)
    if detected:
        log.info("check_message_existence: scanned=%d, owner_deletions_detected=%d", len(rows), detected)
    return detected

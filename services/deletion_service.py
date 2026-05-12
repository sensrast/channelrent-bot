import logging
import asyncio
from telegram import Bot
import config
from database.queries.bookings import list_active_expired, list_active_bookings
from database.queries.channels import get_channel
from services.broadcast_service import delete_from_channel, message_exists
from services.refund_service import settle_booking
from services.notification_service import notify

log = logging.getLogger(__name__)

_delete_attempts: dict[int, int] = {}
_MAX_DELETE_ATTEMPTS = 6

def _probe_target():
    return config.SUPERADMIN_IDS[0] if config.SUPERADMIN_IDS else None

async def _try_expire_one(bot: Bot, b):
    bid = b["booking_id"]
    try:
        ch = await get_channel(b["channel_id"])
        if not ch:
            await settle_booking(bid, "message_lost")
            _delete_attempts.pop(bid, None)
            return
        if not b.get("telegram_message_id"):
            await settle_booking(bid, "message_lost")
            _delete_attempts.pop(bid, None)
            return
        ok = await delete_from_channel(bot, ch["telegram_chat_id"], b["telegram_message_id"])
        if not ok:
            attempts = _delete_attempts.get(bid, 0) + 1
            _delete_attempts[bid] = attempts
            log.warning("expiry deletion failed for booking %s (attempt %s/%s) on chat %s msg %s",
                        bid, attempts, _MAX_DELETE_ATTEMPTS, ch["telegram_chat_id"], b["telegram_message_id"])
            present = await message_exists(
                bot, ch["telegram_chat_id"], b["telegram_message_id"],
                probe_chat_id=_probe_target(),
                inline_buttons_json=b.get("inline_buttons_json"),
            )
            if present and attempts < _MAX_DELETE_ATTEMPTS:
                return
            dtype = "message_lost"
        else:
            dtype = "scheduled"
        _delete_attempts.pop(bid, None)
        refund, owner_earn, commission = await settle_booking(bid, dtype)
        await notify(bot, b["advertiser_id"], "post_completed",
            f"✅ <b>Ad completed</b>
Booking: <code>{b['booking_ref']}</code>
Channel: {ch['title']}
💰 Credits used: {b['total_credits_charged']-refund}
" + (f"🔁 Refund: {refund} credits" if refund>0 else ""),
            booking_id=bid)
        await notify(bot, b["owner_id"], "post_completed",
            f"✅ <b>Booking completed</b>
Booking: <code>{b['booking_ref']}</code>
Channel: {ch['title']}
💰 You earned: {owner_earn} credits",
            booking_id=bid)
    except Exception as e:
        log.exception("expired processing failed for booking %s: %s", b.get("booking_id"), e)

async def process_expired(bot: Bot):
    rows = await list_active_expired()
    if not rows: return
    await asyncio.gather(*[_try_expire_one(bot, b) for b in rows], return_exceptions=True)

async def _check_one_existence(bot: Bot, b, target):
    try:
        ch = await get_channel(b["channel_id"])
        if not ch or not b["telegram_message_id"]:
            return
        present = await message_exists(
            bot, ch["telegram_chat_id"], b["telegram_message_id"],
            probe_chat_id=target,
            inline_buttons_json=b.get("inline_buttons_json"),
        )
        if present:
            return
        refund, owner_earn, _ = await settle_booking(b["booking_id"], "owner_deleted")
        await notify(bot, b["advertiser_id"], "owner_deleted_post",
            f"⚠️ <b>Your ad was removed early by the channel owner</b>
"
            f"Booking: <code>{b['booking_ref']}</code>
Channel: {ch['title']}
"
            f"💰 Full refund: {refund} credits returned to your wallet.",
            booking_id=b["booking_id"])
        await notify(bot, b["owner_id"], "owner_deleted_post",
            f"ℹ️ Booking <code>{b['booking_ref']}</code> on {ch['title']} was no longer present. "
            f"The advertiser was fully refunded. Repeated early deletions affect your reliability score.",
            booking_id=b["booking_id"])
    except Exception as e:
        log.debug("existence check failed for %s: %s", b.get("booking_id"), e)

async def check_message_existence(bot: Bot):
    target = _probe_target()
    rows = await list_active_bookings()
    if not rows: return
    await asyncio.gather(*[_check_one_existence(bot, b, target) for b in rows], return_exceptions=True)

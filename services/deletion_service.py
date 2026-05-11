import logging
from telegram import Bot
from database.queries.bookings import list_active_expired, list_active_bookings, update_booking
from database.queries.channels import get_channel
from services.broadcast_service import delete_from_channel, message_exists
from services.refund_service import settle_booking
from services.notification_service import notify
import config

log = logging.getLogger(__name__)

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
                f"✅ <b>Ad completed</b>\nBooking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n💰 Credits used: {b['total_credits_charged']-refund}\n{('🔁 Refund: '+str(refund)+' credits') if refund>0 else ''}", booking_id=b["booking_id"])
            await notify(bot, b["owner_id"], "post_completed",
                f"✅ <b>Booking completed</b>\nBooking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n💰 You earned: {owner_earn} credits", booking_id=b["booking_id"])
        except Exception as e:
            log.exception("expired processing failed for booking %s: %s", b.get("booking_id"), e)

async def check_message_existence(bot: Bot):
    rows = await list_active_bookings()
    if not config.SUPERADMIN_IDS:
        return
    target = config.SUPERADMIN_IDS[0]
    for b in rows[:20]:
        try:
            ch = await get_channel(b["channel_id"])
            if not ch or not b["telegram_message_id"]: continue
            exists = await message_exists(bot, ch["telegram_chat_id"], b["telegram_message_id"], target)
            if not exists:
                refund, owner_earn, _ = await settle_booking(b["booking_id"], "owner_deleted")
                await notify(bot, b["advertiser_id"], "owner_deleted_post",
                    f"⚠️ <b>Your ad was removed early</b>\nBooking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n💰 Full refund: {refund} credits returned.", booking_id=b["booking_id"])
                await notify(bot, b["owner_id"], "owner_deleted_post",
                    f"ℹ️ The booking <code>{b['booking_ref']}</code> was no longer present on your channel. The advertiser was fully refunded.", booking_id=b["booking_id"])
        except Exception as e:
            log.debug("existence check failed: %s", e)

import logging
from telegram import Bot
from telegram.error import BadRequest, Forbidden, TelegramError
from database.queries.bookings import list_active_expired, list_active_bookings
from database.queries.channels import get_channel
from services.broadcast_service import delete_from_channel
from services.refund_service import settle_booking
from services.notification_service import notify

log = logging.getLogger(__name__)

async def _message_present(bot: Bot, chat_id, message_id, inline_buttons_json=None) -> bool:
    """Probe whether a posted ad still exists without altering it.
    Re-applies the original markup → Telegram replies 'message is not modified' if it still exists,
    and 'message to edit not found' if the owner deleted it.
    """
    from services.broadcast_service import _buttons
    markup = _buttons(inline_buttons_json)
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
        return True
    except BadRequest as e:
        msg = str(e).lower()
        if "not modified" in msg or "exactly the same" in msg or "are exactly" in msg:
            return True
        if "not found" in msg or "to edit" in msg or "can't be edited" in msg or "message identifier" in msg:
            return False
        log.debug("edit probe ambiguous: %s", e)
        return True
    except Forbidden:
        return True
    except TelegramError as e:
        log.debug("edit probe error: %s", e)
        return True

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

async def check_message_existence(bot: Bot):
    """Detect owner-side deletion of the ad and fully refund the advertiser."""
    rows = await list_active_bookings()
    for b in rows:
        try:
            ch = await get_channel(b["channel_id"])
            if not ch or not b["telegram_message_id"]:
                continue
            present = await _message_present(bot, ch["telegram_chat_id"], b["telegram_message_id"], b.get("inline_buttons_json"))
            if present:
                continue
            refund, owner_earn, _ = await settle_booking(b["booking_id"], "owner_deleted")
            await notify(bot, b["advertiser_id"], "owner_deleted_post",
                f"⚠️ <b>Your ad was removed early by the channel owner</b>\n"
                f"Booking: <code>{b['booking_ref']}</code>\nChannel: {ch['title']}\n"
                f"💰 Full refund: {refund} credits returned to your wallet.",
                booking_id=b["booking_id"])
            await notify(bot, b["owner_id"], "owner_deleted_post",
                f"ℹ️ Booking <code>{b['booking_ref']}</code> on {ch['title']} was no longer present. "
                f"The advertiser was fully refunded. Repeated early deletions affect your reliability score.",
                booking_id=b["booking_id"])
        except Exception as e:
            log.debug("existence check failed for %s: %s", b.get("booking_id"), e)

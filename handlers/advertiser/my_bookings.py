import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import kb, back
from utils.formatters import fmt_time_remaining, status_emoji
from database.queries.bookings import list_advertiser_bookings, get_booking
from database.queries.channels import get_channel
from services.broadcast_service import delete_from_channel, message_exists
from services.refund_service import settle_booking
from services.notification_service import notify
from database.pool import db
import config

log = logging.getLogger(__name__)

async def _reconcile_active(bot, booking):
    """If an 'active' booking's channel post is gone, settle as owner_deleted,
    refund the advertiser and notify both parties. Returns True if reconciled."""
    if not booking or booking["status"] != "active" or not booking.get("telegram_message_id"):
        return False
    try:
        from datetime import datetime, timezone, timedelta
        sched = booking.get("scheduled_delete_at")
        if sched is not None:
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
            # If the scheduled deletion is imminent or already past, let the
            # scheduler's process_expired() handle it as a normal completion.
            # Otherwise we race and falsely tag a clean expiry as "removed early".
            if datetime.now(timezone.utc) >= sched - timedelta(seconds=90):
                return False
        ch = await get_channel(booking["channel_id"])
        if not ch:
            return False
        probe = config.SUPERADMIN_IDS[0] if config.SUPERADMIN_IDS else None
        present = await message_exists(
            bot, ch["telegram_chat_id"], booking["telegram_message_id"],
            probe_chat_id=probe,
            inline_buttons_json=booking.get("inline_buttons_json"),
        )
        if present:
            return False
        refund, owner_earn, _ = await settle_booking(booking["booking_id"], "owner_deleted")
        try:
            await notify(bot, booking["advertiser_id"], "owner_deleted_post",
                f"⚠️ <b>Your ad was removed early by the channel owner</b>\n"
                f"Booking: <code>{booking['booking_ref']}</code>\nChannel: {ch['title']}\n"
                f"💰 Full refund: {refund} credits returned to your wallet.",
                booking_id=booking["booking_id"])
        except Exception: pass
        try:
            await notify(bot, booking["owner_id"], "owner_deleted_post",
                f"ℹ️ Booking <code>{booking['booking_ref']}</code> on {ch['title']} was no longer present. "
                f"The advertiser was fully refunded. Repeated early deletions affect your reliability score.",
                booking_id=booking["booking_id"])
        except Exception: pass
        return True
    except Exception as e:
        log.debug("reconcile_active err: %s", e)
        return False

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_advertiser_bookings(q.from_user.id, limit=20)
    for b in rows:
        if b["status"] == "active":
            full = await get_booking(b["booking_id"])
            await _reconcile_active(context.bot, full)
    rows = await list_advertiser_bookings(q.from_user.id, limit=20)
    if not rows:
        await q.edit_message_text("📋 <b>My Bookings</b>\n\nNo bookings yet.\n\nTap Browse to start.",
            parse_mode="HTML", reply_markup=kb([[("🔍 Browse","adv:browse")], back("home")]))
        return
    txt = "📋 <b>My Bookings</b>\n"
    kb_rows = []
    for b in rows[:15]:
        emoji = status_emoji(b["status"])
        line = f"\n{emoji} <code>{b['booking_ref']}</code> • {b['channel_title']} • {b['status']}"
        if b["status"] == "active":
            line += f" • {fmt_time_remaining(b['scheduled_delete_at'])}"
        txt += line
        kb_rows.append([(f"👁️ {b['booking_ref']}", f"adv:bk:{b['booking_id']}")])
    kb_rows.append(back("home"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

async def view_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bid = int(q.data.split(":")[2])
    b = await get_booking(bid)
    if not b or b["advertiser_id"] != q.from_user.id:
        await q.edit_message_text("Not found.", reply_markup=kb([back("adv:bookings")]))
        return
    if b["status"] == "active":
        if await _reconcile_active(context.bot, b):
            b = await get_booking(bid)
    txt = (f"📋 <b>{b['booking_ref']}</b>\n\n"
           f"📢 Channel: {b['channel_title']}\n"
           f"⏱️ Duration: {b['duration_hours']}h\n"
           f"📦 Status: <b>{b['status']}</b>\n"
           f"💰 Charged: {b['total_credits_charged']} cr\n"
           f"🔁 Refunded: {b['credits_refunded']} cr\n")
    if b["status"] == "active":
        txt += f"⏳ Time left: {fmt_time_remaining(b['scheduled_delete_at'])}\n"
    rows = []
    if b["status"] == "active":
        rows.append([("🛑 Delete Early", f"adv:bk:del:{bid}")])
    if b["status"] == "pending_approval":
        rows.append([("❌ Cancel", f"adv:bk:cancel:{bid}")])
    rows.append(back("adv:bookings"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def delete_early_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bid = int(q.data.split(":")[3])
    b = await get_booking(bid)
    if not b or b["advertiser_id"] != q.from_user.id or b["status"] != "active":
        await q.edit_message_text("Invalid.", reply_markup=kb([back("adv:bookings")]))
        return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    posted = b["posted_at"]
    if posted and posted.tzinfo is None: posted = posted.replace(tzinfo=timezone.utc)
    elapsed_h = max(0,(now - posted).total_seconds()/3600)
    used = min(int(round(elapsed_h * b["price_per_hour_credits"])), b["total_credits_charged"])
    refund = b["total_credits_charged"] - used
    txt = (f"⚠️ <b>Early Deletion</b>\n\n"
           f"Booking: <code>{b['booking_ref']}</code>\n"
           f"Used: ~{used} cr\nRefund: <b>{refund} cr</b>\n\nProceed?")
    rows = [[("✅ Yes, Delete & Refund", f"adv:bk:delgo:{bid}"),("❌ No", f"adv:bk:{bid}")]]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def delete_early_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Processing...")
    bid = int(q.data.split(":")[3])
    b = await get_booking(bid)
    if not b or b["advertiser_id"] != q.from_user.id or b["status"] != "active":
        await q.edit_message_text("Invalid.", reply_markup=kb([back("adv:bookings")]))
        return
    await delete_from_channel(context.bot, b["telegram_chat_id"], b["telegram_message_id"])
    refund, owner_earn, _ = await settle_booking(bid, "advertiser_requested")
    await q.edit_message_text(f"✅ {refund} credits refunded.\nThank you!", reply_markup=kb([back("adv:bookings")]))
    await notify(context.bot, b["owner_id"], "early_advertiser",
        f"ℹ️ Advertiser ended booking <code>{b['booking_ref']}</code> early.\n💰 You earned: {owner_earn} cr",
        booking_id=bid)

async def cancel_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bid = int(q.data.split(":")[3])
    b = await get_booking(bid)
    if not b or b["advertiser_id"] != q.from_user.id or b["status"] != "pending_approval":
        await q.edit_message_text("Invalid.", reply_markup=kb([back("adv:bookings")]))
        return
    refund, _, _ = await settle_booking(bid, "advertiser_requested")
    await q.edit_message_text(f"❌ Cancelled. Refunded {refund} cr.", reply_markup=kb([back("adv:bookings")]))

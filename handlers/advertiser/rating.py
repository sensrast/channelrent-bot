import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.pool import db
from database.queries.bookings import get_booking
from database.queries.channels import update_rating

log = logging.getLogger(__name__)


async def submit_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        parts = (q.data or "").split(":")
        bid = int(parts[2])
        stars = int(parts[3])
    except Exception:
        await q.answer("Invalid", show_alert=True)
        return
    if stars < 1 or stars > 5:
        await q.answer("Invalid rating", show_alert=True)
        return
    b = await get_booking(bid)
    if not b or b["advertiser_id"] != q.from_user.id:
        await q.answer("Not allowed", show_alert=True)
        return
    if b["status"] not in ("completed", "completed_early"):
        await q.answer("Booking not completed yet", show_alert=True)
        return
    existing = await db.fetchval("SELECT review_id FROM reviews WHERE booking_id=$1", bid)
    if existing:
        await q.answer("You already rated this booking", show_alert=True)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    try:
        await db.execute(
            "INSERT INTO reviews (booking_id, channel_id, advertiser_id, rating) VALUES ($1,$2,$3,$4)",
            bid, b["channel_id"], b["advertiser_id"], stars)
        await db.execute(
            "UPDATE bookings SET advertiser_rating=$2 WHERE booking_id=$1", bid, stars)
        await update_rating(b["channel_id"])
    except Exception as e:
        log.exception("rating insert failed: %s", e)
        await q.answer("Could not save rating", show_alert=True)
        return
    await q.answer(f"Thanks for rating {stars}\u2b50")
    try:
        stars_text = "\u2b50" * stars
        new_text = (q.message.text_html or q.message.text or "") + f"\n\n\u2705 You rated: {stars_text}"
        await q.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)
    except Exception:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

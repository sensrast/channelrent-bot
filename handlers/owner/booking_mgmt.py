from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
import json
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.keyboards import kb, back
from database.queries.bookings import get_booking, update_booking
from database.queries.credits import adjust_credits
from database.pool import db
from services.broadcast_service import post_to_channel
from services.refund_service import settle_booking
from services.notification_service import notify

log = logging.getLogger(__name__)

REJECT_REASON = 0


def _action_kb(bid):
    return kb([
        [("👁️ Preview Ad", f"owner:prev:{bid}")],
        [("✅ Approve", f"owner:apv:{bid}"), ("❌ Reject", f"owner:rej:{bid}")],
        back("owner:bookings"),
    ])


def _inline_buttons_markup(buttons_json):
    if not buttons_json:
        return None
    try:
        data = buttons_json if isinstance(buttons_json, list) else json.loads(buttons_json)
        return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url) for label, url in data]])
    except Exception:
        return None


async def preview_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Loading preview…")
    try:
        bid = int(q.data.split(":")[2])
    except Exception:
        await q.answer("Invalid", show_alert=True)
        return
    b = await get_booking(bid)
    if not b or b["owner_id"] != q.from_user.id:
        await q.answer("Not found", show_alert=True)
        return
    chat_id = q.message.chat_id
    header = (
        f"👁️ <b>Ad Preview</b>\n"
        f"Ref: <code>{b['booking_ref']}</code>\n"
        f"Channel: {b['channel_title']}\n"
        f"Duration: {b['duration_hours']}h\n"
        f"Status: {b['status']}"
    )
    try:
        await context.bot.send_message(chat_id, header, parse_mode="HTML")
    except Exception as e:
        log.warning("preview header send failed: %s", e)
    markup = _inline_buttons_markup(b.get("inline_buttons_json"))
    ct = b.get("content_type")
    try:
        if ct == "text":
            await context.bot.send_message(chat_id, b.get("content_text") or "(empty)", reply_markup=markup, disable_web_page_preview=False)
        elif ct == "photo" and b.get("media_file_id"):
            await context.bot.send_photo(chat_id, b["media_file_id"], caption=(b.get("caption") or ""), reply_markup=markup)
        elif ct == "document" and b.get("media_file_id"):
            await context.bot.send_document(chat_id, b["media_file_id"], caption=(b.get("caption") or ""), reply_markup=markup)
        else:
            await context.bot.send_message(chat_id, "(no preview available)")
    except Exception as e:
        log.exception("preview send failed: %s", e)
        try:
            await context.bot.send_message(chat_id, f"⚠️ Could not render preview: {e}")
        except Exception:
            pass
    if b["status"] == "pending_approval":
        try:
            await context.bot.send_message(chat_id, "Review the ad above, then choose an action:", reply_markup=_action_kb(bid))
        except Exception:
            pass


async def approve_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Approving...")
    try:
        bid = int(q.data.split(":")[2])
    except Exception:
        await q.answer("Invalid", show_alert=True)
        return
    b = await get_booking(bid)
    if not b or b["owner_id"] != q.from_user.id or b["status"] != "pending_approval":
        try:
            await q.edit_message_text("Invalid or already processed.", reply_markup=kb([back("owner:bookings")]))
        except Exception:
            await context.bot.send_message(q.message.chat_id, "Invalid or already processed.", reply_markup=kb([back("owner:bookings")]))
        return
    try:
        wm = (await db.fetchval("SELECT value FROM platform_settings WHERE key='watermark_enabled'") or "true").lower() == "true"
        msg_id = await post_to_channel(context.bot, dict(b), watermark=wm)
        now = datetime.now(timezone.utc)
        sched = now + timedelta(hours=b["duration_hours"])
        await update_booking(bid, status="active", approved_at=now, posted_at=now, scheduled_delete_at=sched, telegram_message_id=msg_id)
        confirm_text = f"✅ Approved & posted. <code>{b['booking_ref']}</code>"
        try:
            await q.edit_message_text(confirm_text, parse_mode="HTML", reply_markup=kb([back("owner:bookings")]))
        except Exception:
            await context.bot.send_message(q.message.chat_id, confirm_text, parse_mode="HTML", reply_markup=kb([back("owner:bookings")]))
        await notify(context.bot, b["advertiser_id"], "booking_approved",
            f"✅ <b>Approved!</b>\nBooking: <code>{b['booking_ref']}</code>\nLive until {sched:%Y-%m-%d %H:%M UTC}",
            booking_id=bid)
    except Exception as e:
        log.exception("approve post failed: %s", e)
        try:
            await q.edit_message_text("❌ Failed to post. Try again.", reply_markup=kb([back("owner:bookings")]))
        except Exception:
            await context.bot.send_message(q.message.chat_id, "❌ Failed to post. Try again.", reply_markup=kb([back("owner:bookings")]))

async def reject_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bid = int(q.data.split(":")[2])
    b = await get_booking(bid)
    if not b or b["owner_id"] != q.from_user.id or b["status"] != "pending_approval":
        try:
            await q.edit_message_text("Invalid.", reply_markup=kb([back("owner:bookings")]))
        except Exception:
            await context.bot.send_message(q.message.chat_id, "Invalid.", reply_markup=kb([back("owner:bookings")]))
        return ConversationHandler.END
    context.user_data["reject_bid"] = bid
    try:
        await q.edit_message_text("Enter reason for rejection:")
    except Exception:
        await context.bot.send_message(q.message.chat_id, "Enter reason for rejection:")
    return REJECT_REASON

async def reject_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bid = context.user_data.pop("reject_bid", None)
    reason = update.message.text[:300]
    if not bid:
        await update.message.reply_text("Session expired.")
        return ConversationHandler.END
    b = await get_booking(bid)
    if not b: return ConversationHandler.END
    async with db.acquire() as conn:
        async with conn.transaction():
            await adjust_credits(conn, b["advertiser_id"], b["total_credits_charged"],
                "booking_cancelled", description=f"Rejected {b['booking_ref']}: {reason}", booking_id=bid)
            await conn.execute("UPDATE bookings SET status='rejected', rejection_reason=$2 WHERE booking_id=$1", bid, reason)
    await update.message.reply_text("❌ Rejected and refunded.", reply_markup=kb([back("owner:bookings")]))
    await notify(context.bot, b["advertiser_id"], "booking_rejected",
        f"❌ <b>Booking rejected</b>\n<code>{b['booking_ref']}</code>\nReason: {reason}\n💰 Refunded: {b['total_credits_charged']} cr", booking_id=bid)
    return ConversationHandler.END

def build_reject_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(reject_start, pattern=r"^owner:rej:\d+$")],
        states={REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_finish)]},
        fallbacks=[_CmdHandler("cancel", _univ_cancel)],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

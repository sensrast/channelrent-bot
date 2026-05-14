from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
import json
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.keyboards import kb, kb_url, back
from utils.channel_links import get_channel_link
from utils.formatters import fmt_credits
from utils.validators import parse_int, parse_buttons
from database.pool import db
from database.queries.channels import get_channel
from database.queries.bookings import generate_booking_ref, create_booking, update_booking, count_advertiser_active, get_booking
from database.queries.credits import adjust_credits
from services.pricing_engine import commission_split
from services.broadcast_service import post_to_channel
from services.notification_service import notify

log = logging.getLogger(__name__)

PICK_DURATION, CUSTOM_DURATION, GET_CONTENT, ASK_BUTTONS, GET_BUTTONS, CONFIRM = range(6)

async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ch_id = int(q.data.split(":")[2])
    c = await get_channel(ch_id)
    if not c or not c["is_listed"] or c["is_suspended"] or c["is_paused"]:
        await q.edit_message_text("This channel is not available right now.", reply_markup=kb([back("adv:browse")]))
        return ConversationHandler.END
    if c["owner_id"] == q.from_user.id:
        await q.edit_message_text("You cannot book your own channel.", reply_markup=kb([back("adv:browse")]))
        return ConversationHandler.END
    active = await count_advertiser_active(q.from_user.id)
    max_active = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='max_active_bookings_per_advertiser'") or 20)
    if active >= max_active:
        await q.edit_message_text(f"You have {active} active/pending bookings (limit {max_active}).", reply_markup=kb([back("adv:bookings")]))
        return ConversationHandler.END
    context.user_data["booking"] = {"channel_id": ch_id, "price": c["final_price_credits"]}
    bal = await db.fetchval("SELECT credits_balance FROM users WHERE user_id=$1", q.from_user.id)
    price = c["final_price_credits"]
    txt = (f"⏱️ <b>Choose Duration</b>\n\n"
           f"📢 {c['title']}\n"
           f"💰 Rate: {price} cr/hr\n"
           f"💎 Your balance: {fmt_credits(bal)} cr")
    rows = [
        [(f"1h — {price} cr","adv:bf:d:1"),(f"3h — {price*3} cr","adv:bf:d:3")],
        [(f"6h — {price*6} cr","adv:bf:d:6"),(f"12h — {price*12} cr","adv:bf:d:12")],
        [(f"24h — {price*24} cr","adv:bf:d:24"),(f"48h — {price*48} cr","adv:bf:d:48")],
        [(f"7d — {price*168} cr","adv:bf:d:168")],
        [("✏️ Custom","adv:bf:custom")],
        [("❌ Cancel","adv:bf:cancel")],
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return PICK_DURATION

async def pick_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "adv:bf:cancel":
        context.user_data.pop("booking", None)
        await q.edit_message_text("❌ Booking cancelled.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    if q.data == "adv:bf:custom":
        await q.edit_message_text("Enter custom duration in hours (1-168):")
        return CUSTOM_DURATION
    hours = int(q.data.split(":")[-1])
    return await _validate_duration(q, context, hours)

async def _validate_duration(target, context, hours):
    b = context.user_data["booking"]
    c = await get_channel(b["channel_id"])
    if hours < c["min_booking_hours"] or hours > c["max_booking_hours"]:
        msg = f"Duration must be between {c['min_booking_hours']} and {c['max_booking_hours']} hours."
        if hasattr(target,"edit_message_text"):
            await target.edit_message_text(msg)
        else: await target.reply_text(msg)
        return CUSTOM_DURATION
    total = hours * b["price"]
    bal = await db.fetchval("SELECT credits_balance FROM users WHERE user_id=$1", target.from_user.id)
    if bal < total and target.from_user.id not in config.SUPERADMIN_IDS:
        txt = (f"❌ <b>Insufficient Credits</b>\n\nRequired: {total} cr\nBalance: {bal} cr\nShortfall: {total-bal} cr")
        rows = [[("💰 Top Up","adv:topup")], back("adv:browse")]
        if hasattr(target,"edit_message_text"):
            await target.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
        else: await target.reply_text(txt, parse_mode="HTML", reply_markup=kb(rows))
        return ConversationHandler.END
    b["hours"] = hours; b["total"] = total
    txt = (f"📤 <b>Send Your Ad Content</b>\n\n"
           f"Send text (with links) or an image. ❌ No videos, GIFs, MP4s, or stickers.\n\n"
           f"─── Channel Rules ───\n"
           f"✅ {c['allowed_content']}\n"
           f"❌ {c['forbidden_content']}\n\n"
           f"Send /cancel to abort.")
    if hasattr(target,"edit_message_text"):
        await target.edit_message_text(txt, parse_mode="HTML")
    else:
        await target.reply_text(txt, parse_mode="HTML")
    return GET_CONTENT

async def custom_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = parse_int(update.message.text, 1, 168)
    if not val:
        await update.message.reply_text("Invalid. Enter a number 1-168.")
        return CUSTOM_DURATION
    return await _validate_duration(update.message, context, val)

async def get_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    b = context.user_data.get("booking")
    if not b:
        await m.reply_text("Session expired.")
        return ConversationHandler.END
    if m.video or m.animation or m.sticker or m.video_note or m.voice or m.audio:
        await m.reply_text("❌ Videos, GIFs, MP4s, stickers, voice and audio are not allowed. Please send text (with links) or an image.")
        return GET_CONTENT
    if m.document:
        mt = (getattr(m.document, "mime_type", "") or "").lower()
        fn = (getattr(m.document, "file_name", "") or "").lower()
        if mt.startswith("video/") or mt == "image/gif" or fn.endswith((".mp4", ".mov", ".webm", ".gif", ".mkv", ".avi")):
            await m.reply_text("❌ Video/MP4/GIF files are not allowed. Please send text (with links) or an image.")
            return GET_CONTENT
        b["content_type"]="document"; b["media_file_id"]=m.document.file_id; b["caption"]=m.caption or ""; b["content_text"]=None
    elif m.photo:
        b["content_type"]="photo"; b["media_file_id"]=m.photo[-1].file_id; b["caption"]=m.caption or ""; b["content_text"]=None
    elif m.text:
        b["content_type"]="text"; b["content_text"]=m.text; b["caption"]=None; b["media_file_id"]=None
    else:
        await m.reply_text("❌ Unsupported content. Allowed: text (with links) or photo only.")
        return GET_CONTENT
    await m.reply_text("🔘 Add clickable buttons? (Optional)", reply_markup=kb([[("➕ Add Buttons","adv:bf:btn:yes"),("⏩ Skip","adv:bf:btn:no")]]))
    return ASK_BUTTONS

async def ask_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":no"):
        return await _show_confirm(q, context)
    await q.edit_message_text("Send buttons one per line in this format:\n<code>Label - https://url</code>\n\nMax 5 buttons.", parse_mode="HTML")
    return GET_BUTTONS

async def get_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = parse_buttons(update.message.text)
    if not buttons:
        await update.message.reply_text("Invalid format. Try again, or /cancel.")
        return GET_BUTTONS
    context.user_data["booking"]["buttons"] = buttons
    return await _show_confirm(update.message, context)

async def _show_confirm(target, context):
    bot = context.bot
    b = context.user_data["booking"]
    c = await get_channel(b["channel_id"])
    bal = await db.fetchval("SELECT credits_balance FROM users WHERE user_id=$1", target.from_user.id)
    btns = b.get("buttons")
    btn_preview = ""
    if btns:
        btn_preview = "\n🔘 Buttons: " + ", ".join(x[0] for x in btns)
    txt = (f"📋 <b>Confirm Booking</b>\n\n"
           f"📢 Channel: {c['title']}\n"
           f"⏱️ Duration: {b['hours']}h\n"
           f"💰 Total: <b>{b['total']} credits</b>\n"
           f"💎 Balance: {bal} → {bal - b['total']} after\n"
           f"📦 Content: {b['content_type']}"
           f"{btn_preview}\n\n"
           f"{'⚡ Auto-approve: Ad posts immediately.' if c['auto_approve'] else '🔍 Manual approval: Owner will review.'}")
    rows = [[("✅ Confirm & Pay","adv:bf:confirm","cd"),("❌ Cancel","adv:bf:cancel","cd")]]
    try:
        link = await get_channel_link(c, bot=bot)
    except Exception:
        link = None
    if link:
        rows.insert(0, [("🔗 Visit Channel", link, "url")])
    markup = kb_url(rows)
    if hasattr(target,"edit_message_text"):
        await target.edit_message_text(txt, parse_mode="HTML", reply_markup=markup)
    else:
        await target.reply_text(txt, parse_mode="HTML", reply_markup=markup)
    return CONFIRM

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Processing...")
    if q.data == "adv:bf:cancel":
        context.user_data.pop("booking", None)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    b = context.user_data.get("booking")
    if not b:
        await q.edit_message_text("Session expired.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    c = await get_channel(b["channel_id"])
    ref = await generate_booking_ref()
    user_id = q.from_user.id
    total = b["total"]
    buttons_json = json.dumps(b.get("buttons")) if b.get("buttons") else None
    auto = c["auto_approve"]
    status = "approved" if auto else "pending_approval"
    try:
        async with db.acquire() as conn:
            async with conn.transaction():
                booking_id = await create_booking(conn,
                    booking_ref=ref, advertiser_id=user_id, channel_id=c["channel_id"], owner_id=c["owner_id"],
                    content_type=b["content_type"], content_text=b.get("content_text"),
                    media_file_id=b.get("media_file_id"), caption=b.get("caption"),
                    inline_buttons_json=buttons_json, duration_hours=b["hours"],
                    price_per_hour_credits=b["price"], total_credits_charged=total,
                    status=status, approval_required=not auto)
                if user_id not in config.SUPERADMIN_IDS:
                    await adjust_credits(conn, user_id, -total, "booking_charge",
                        description=f"Booking {ref}", booking_id=booking_id)
                await conn.execute("UPDATE users SET total_bookings_made=total_bookings_made+1, is_advertiser=TRUE WHERE user_id=$1", user_id)
    except ValueError as e:
        await q.edit_message_text(f"❌ {e}", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    booking = await get_booking(booking_id)
    if auto:
        try:
            wm = (await db.fetchval("SELECT value FROM platform_settings WHERE key='watermark_enabled'") or "true").lower() == "true"
            msg_id = await post_to_channel(context.bot, dict(booking), watermark=wm)
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            sched = now + timedelta(hours=b["hours"])
            await update_booking(booking_id, status="active", posted_at=now, scheduled_delete_at=sched, telegram_message_id=msg_id, approved_at=now)
            await q.edit_message_text(f"✅ <b>Your ad is LIVE!</b>\n\nBooking: <code>{ref}</code>\n⏱️ Ends: {sched:%Y-%m-%d %H:%M UTC}\n💰 Credits spent: {total}",
                                      parse_mode="HTML", reply_markup=kb([[("📋 My Bookings","adv:bookings")],back("home")]))
            await notify(context.bot, c["owner_id"], "booking_active",
                f"🚀 <b>New ad live on {c['title']}!</b>\nBooking: <code>{ref}</code>\nYou'll earn up to {commission_split(total)[1]} cr when it completes.",
                booking_id=booking_id)
        except Exception as e:
            log.exception("post failed: %s", e)
            async with db.acquire() as conn:
                async with conn.transaction():
                    if user_id not in config.SUPERADMIN_IDS:
                        await adjust_credits(conn, user_id, total, "booking_cancelled", description=f"Auto-refund: post failed for {ref}", booking_id=booking_id)
                    await update_booking(booking_id, status="cancelled", cancelled_by="system", cancellation_reason=str(e)[:200], cancelled_at_=None)
            await q.edit_message_text("❌ Could not post the ad. Credits refunded.", reply_markup=kb([back("home")]))
    else:
        await q.edit_message_text(f"⏳ <b>Booking submitted</b>\n\nRef: <code>{ref}</code>\nCredits held: {total}\n\nOwner will review.",
                                  parse_mode="HTML", reply_markup=kb([[("📋 My Bookings","adv:bookings")],back("home")]))
        await notify(context.bot, c["owner_id"], "booking_received",
            f"📋 <b>New booking request</b>\nRef: <code>{ref}</code>\nDuration: {b['hours']}h\nYou'll earn: {commission_split(total)[1]} cr\n\nReview in your dashboard.",
            booking_id=booking_id,
            reply_markup=kb([
                [("👁️ Preview Ad", f"owner:prev:{booking_id}")],
                [("✅ Approve",f"owner:apv:{booking_id}"),("❌ Reject",f"owner:rej:{booking_id}")],
            ]))
    context.user_data.pop("booking", None)
    return ConversationHandler.END

def build_booking_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(book_start, pattern=r"^adv:book:\d+$")],
        states={
            PICK_DURATION: [CallbackQueryHandler(pick_duration, pattern=r"^adv:bf:(d:\d+|custom|cancel)$")],
            CUSTOM_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_duration)],
            GET_CONTENT: [MessageHandler((filters.TEXT|filters.PHOTO|filters.Document.ALL|filters.VIDEO|filters.ANIMATION|filters.Sticker.ALL|filters.AUDIO|filters.VOICE|filters.VIDEO_NOTE) & ~filters.COMMAND, get_content)],
            ASK_BUTTONS: [CallbackQueryHandler(ask_buttons, pattern=r"^adv:bf:btn:(yes|no)$")],
            GET_BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_buttons)],
            CONFIRM: [CallbackQueryHandler(confirm_booking, pattern=r"^adv:bf:(confirm|cancel)$")],
        },
        fallbacks=[CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern=r"^home$")],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

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

from telegram import Update
from telegram.ext import ContextTypes
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.pool import db

@superadmin_only
async def bookings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await db.fetch("SELECT b.*, c.title as channel_title FROM bookings b JOIN channels c ON c.channel_id=b.channel_id ORDER BY booked_at DESC LIMIT 20")
    txt = "📋 <b>Recent Bookings</b>\n"
    for b in rows:
        txt += f"\n• <code>{b['booking_ref']}</code> • {b['status']} • {b['channel_title']}"
    await q.edit_message_text(txt or "None", parse_mode="HTML", reply_markup=kb([back("admin:panel")]))

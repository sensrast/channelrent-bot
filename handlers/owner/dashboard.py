from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import kb, back
from utils.formatters import fmt_credits, activity_emoji
from database.pool import db
from database.queries.channels import list_owner_channels, get_channel, update_channel
from database.queries.bookings import list_owner_bookings, get_booking
from database.queries.users import get_user

async def my_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_owner_channels(q.from_user.id)
    if not rows:
        await q.edit_message_text("📢 <b>My Channels</b>\n\nNo channels yet.",
            parse_mode="HTML", reply_markup=kb([[("➕ Add Channel","owner:add")],back("home")]))
        return
    txt = f"📢 <b>My Channels ({len(rows)})</b>\n"
    kb_rows = []
    for c in rows[:10]:
        state = "🟢 Active" if c["is_listed"] and not c["is_paused"] and not c["is_suspended"] else "🟡 Paused" if c["is_paused"] else "🔴 Off"
        txt += (f"\n━━━━━━━━━━━━━━━\n📢 <b>{c['title']}</b>\n"
                f"👥 {fmt_credits(c['subscriber_count'])} • {activity_emoji(c['activity_tier'])} {c['activity_tier'].upper()}\n"
                f"💰 {c['final_price_credits']} cr/hr • {state}\n"
                f"⭐ {c['rating']:.1f} ({c['rating_count']})")
        kb_rows.append([(f"⚚️ {c['title'][:25]}", f"owner:ch:{c['channel_id']}")])
    kb_rows.append([("➕ Add Channel","owner:add")])
    kb_rows.append(back("home"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

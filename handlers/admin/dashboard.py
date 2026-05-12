from telegram import Update
from telegram.ext import ContextTypes
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from services.analytics_service import get_overview, get_7day_chart, get_top_channels
from utils.formatters import fmt_credits

@superadmin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        send = q.edit_message_text
    else:
        send = update.message.reply_text
    o = await get_overview()
    txt = (f"👑 <b>Admin Panel</b>\n\n"
           f"👥 Users: {fmt_credits(o['total_users'])}\n"
           f"📢 Listed Channels: {fmt_credits(o['listed'])}\n"
           f"📋 Active Bookings: {fmt_credits(o['active'])}\n"
           f"💰 Credits in System: {fmt_credits(o['credits'])}\n"
           f"💸 Revenue Today: {fmt_credits(o['rev_today'])} cr\n"
           f"💸 Revenue Month: {fmt_credits(o['rev_month'])} cr\n"
           f"⏳ Pending Payouts: {o['pending_payouts']} (₹{fmt_credits(o['pending_payout_inr'])})\n"
           f"⏳ Pending Top-ups: {o['pending_topups']} (₹{fmt_credits(o['pending_topup_inr'])})")
    rows = [
        [(f"💳 Top-ups ({o['pending_topups']})","admin:topups"),(f"💸 Payouts ({o['pending_payouts']})","admin:payouts")],
        [("👥 Users","admin:users"),("📢 Channels","admin:channels")],
        [("📋 Bookings","admin:bookings"),("💰 Financial","admin:finance")],
        [("⚙️ Pricing","admin:pricing"),("🔧 Settings","admin:settings")],
        [("📊 Analytics","admin:analytics"),("📢 Broadcast","admin:bcast")],
        back("home"),
    ]
    await send(txt, parse_mode="HTML", reply_markup=kb(rows))

@superadmin_only
async def analytics_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    o = await get_overview()
    chart = await get_7day_chart()
    top = await get_top_channels(5)
    from utils.channel_links import get_channel_link
    lines = []
    for i, r in enumerate(top):
        link = await get_channel_link(r, bot=context.bot)
        title = (r['title'] or '-').replace('<','&lt;').replace('>','&gt;')
        label = f'<a href="{link}">{title}</a>' if link else title
        lines.append(f"{i+1}. {label} — {r['total_bookings']}")
    top_txt = "\n".join(lines) or "—"
    txt = (f"📊 <b>Analytics</b>\n\n"
           f"Users: {o['total_users']}\nActive bookings: {o['active']}\nRev today: {o['rev_today']} cr\nRev month: {o['rev_month']} cr\n\n"
           f"<b>Last 7 days</b>\n<pre>{chart}</pre>\n"
           f"<b>Top channels</b>\n{top_txt}")
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb([back("admin:panel")]))

from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import kb, back
from utils.formatters import fmt_credits, activity_emoji
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
        kb_rows.append([(f"⚙️ {c['title'][:25]}", f"owner:ch:{c['channel_id']}")])
    kb_rows.append([("➕ Add Channel","owner:add")])
    kb_rows.append(back("home"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

async def channel_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[2])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        await q.edit_message_text("Not found.", reply_markup=kb([back("owner:channels")]))
        return
    txt = (f"⚙️ <b>{c['title']}</b>\n\n"
           f"👥 Subscribers: {fmt_credits(c['subscriber_count'])}\n"
           f"👁️ Avg Views: {fmt_credits(c['avg_views_24h'])}\n"
           f"{activity_emoji(c['activity_tier'])} Activity: {c['activity_tier'].upper()} ({c['activity_score']}/100)\n"
           f"💰 Rate: {c['final_price_credits']} cr/hr\n"
           f"📋 Total bookings: {c['total_bookings']}\n"
           f"💰 Revenue: {fmt_credits(c['total_revenue_credits'])} cr\n"
           f"⭐ {c['rating']:.1f} ({c['rating_count']})")
    pause_label = "▶️ Resume Listing" if c["is_paused"] else "⏸️ Pause Listing"
    rows = [
        [("👁️ Refresh Stats", f"owner:ch:refresh:{cid}")],
        [(pause_label, f"owner:ch:pause:{cid}")],
        [("🗑️ Remove Channel", f"owner:ch:rm:{cid}")],
        back("owner:channels"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def channel_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Toggled")
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return
    await update_channel(cid, is_paused=not c["is_paused"])
    q.data = f"owner:ch:{cid}"
    await channel_manage(update, context)

async def channel_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Refreshing...")
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id: return
    try:
        from telegram.error import TelegramError
        count = await context.bot.get_chat_member_count(c["telegram_chat_id"])
        from services.pricing_engine import compute_activity, compute_price_per_hour
        score, tier, eng = compute_activity(count, c["avg_views_24h"])
        price = compute_price_per_hour(count, c["avg_views_24h"], tier)
        await update_channel(cid, subscriber_count=count, activity_score=score, activity_tier=tier, engagement_rate=eng, final_price_credits=price, base_price_credits=price)
    except Exception as e:
        await q.answer(f"Failed: {e}", show_alert=True)
    q.data = f"owner:ch:{cid}"
    await channel_manage(update, context)

async def channel_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id: return
    await update_channel(cid, is_listed=False, is_paused=True, is_active=False)
    await q.edit_message_text(f"🗑️ {c['title']} delisted.", reply_markup=kb([back("owner:channels")]))

async def earnings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = await get_user(q.from_user.id)
    min_payout = 500
    txt = (f"📊 <b>My Earnings</b>\n\n"
           f"💎 Pending: <b>{fmt_credits(user['earnings_pending'])} cr</b>\n"
           f"✅ Paid out: {fmt_credits(user['earnings_paid'])} cr\n\n"
           f"Minimum payout: {min_payout} cr\n")
    rows = [[("💸 Request Payout","owner:payout")], back("home")]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def incoming_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_owner_bookings(q.from_user.id, status_in=["pending_approval","active"], limit=15)
    if not rows:
        await q.edit_message_text("📋 <b>Incoming Bookings</b>\n\nNo active or pending bookings.",
            parse_mode="HTML", reply_markup=kb([back("home")]))
        return
    txt = "📋 <b>Incoming Bookings</b>\n"
    kb_rows = []
    for b in rows:
        txt += f"\n• <code>{b['booking_ref']}</code> • {b['status']} • {b['channel_title']}"
        kb_rows.append([(f"📋 {b['booking_ref']}", f"owner:bk:{b['booking_id']}")])
    kb_rows.append(back("home"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

async def view_owner_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bid = int(q.data.split(":")[2])
    b = await get_booking(bid)
    if not b or b["owner_id"] != q.from_user.id:
        await q.edit_message_text("Not found.", reply_markup=kb([back("owner:bookings")]))
        return
    from services.pricing_engine import commission_split
    _, owner_earn = commission_split(b["total_credits_charged"])
    txt = (f"📋 <b>{b['booking_ref']}</b>\n\nChannel: {b['channel_title']}\nDuration: {b['duration_hours']}h\n"
           f"Status: {b['status']}\nYou'll earn (max): {owner_earn} cr")
    rows = []
    if b["status"] == "pending_approval":
        rows.append([("✅ Approve",f"owner:apv:{bid}"),("❌ Reject",f"owner:rej:{bid}")])
    rows.append(back("owner:bookings"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import kb, back
from utils.formatters import fmt_credits, activity_emoji
from database.queries.channels import get_channel
from database.pool import db

async def channel_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ch_id = int(q.data.split(":")[2])
    c = await get_channel(ch_id)
    if not c:
        await q.edit_message_text("Channel not found.", reply_markup=kb([back("adv:browse")]))
        return
    reviews = await db.fetch("SELECT rating, review_text FROM reviews WHERE channel_id=$1 AND is_visible=TRUE ORDER BY created_at DESC LIMIT 3", ch_id)
    rtxt = ""
    for r in reviews:
        stars = "⭐" * r["rating"]
        rtxt += f"\n{stars} {(r['review_text'] or '')[:70]}"
    if not rtxt: rtxt = "\nNo reviews yet."
    txt = (f"📢 <b>{c['title']}</b>\n"
           f"{('@'+c['username']) if c['username'] else ''}\n\n"
           f"━━━ Channel Info ━━━\n"
           f"👥 Subscribers: {fmt_credits(c['subscriber_count'])}\n"
           f"👁️ Avg Views (24h): {fmt_credits(c['avg_views_24h'])}\n"
           f"📊 Engagement: {c['engagement_rate']}%\n"
           f"{activity_emoji(c['activity_tier'])} Activity: <b>{c['activity_tier'].upper()}</b> ({c['activity_score']}/100)\n"
           f"📂 Category: {c.get('category_name','-')}\n"
           f"🌐 Language: {c['language']}\n"
           f"⭐ {c['rating']:.1f} ({c['rating_count']} reviews)\n"
           f"{'✅ Auto-Approve' if c['auto_approve'] else '🔍 Manual Approval'}\n\n"
           f"━━━ Pricing ━━━\n"
           f"💰 <b>{c['final_price_credits']} credits/hour</b>\n"
           f"📅 {c['final_price_credits']*24} cr/day • {c['final_price_credits']*168} cr/week\n\n"
           f"━━━ Rules ━━━\n"
           f"✅ {c['allowed_content']}\n"
           f"❌ {c['forbidden_content']}\n\n"
           f"━━━ Recent Reviews ━━━{rtxt}")
    rows = [[("📋 Book This Channel", f"adv:book:{ch_id}")], back("adv:browse")]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

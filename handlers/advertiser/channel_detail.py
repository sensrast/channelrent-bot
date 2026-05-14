from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.keyboards import kb, kb_url, back
from utils.channel_links import get_channel_link
from utils.formatters import fmt_credits, activity_emoji
from database.queries.channels import get_channel
from database.pool import db
from services.notification_service import notify_superadmin

REPORT_REASON = 100

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
           f"─── Channel Info ───\n"
           f"👥 Subscribers: {fmt_credits(c['subscriber_count'])}\n"
           f"👁️ Avg Views (24h): {fmt_credits(c['avg_views_24h'])}\n"
           f"📊 Engagement: {c['engagement_rate']}%\n"
           f"{activity_emoji(c['activity_tier'])} Activity: <b>{c['activity_tier'].upper()}</b> ({c['activity_score']}/100)\n"
           f"📂 Category: {c.get('category_name','-')}\n"
           f"🌐 Language: {c['language']}\n"
           f"⭐ {c['rating']:.1f} ({c['rating_count']} reviews)\n"
           f"{'✅ Auto-Approve' if c['auto_approve'] else '🔍 Manual Approval'}\n\n"
           f"─── Pricing ───\n"
           f"💰 <b>{c['final_price_credits']} credits/hour</b>\n"
           f"📅 {c['final_price_credits']*24} cr/day • {c['final_price_credits']*168} cr/week\n\n"
           f"─── Rules ───\n"
           f"✅ {c['allowed_content']}\n"
           f"❌ {c['forbidden_content']}\n\n"
           f"─── Recent Reviews ───{rtxt}")
    is_private = not c.get("username")
    link = await get_channel_link(c, bot=context.bot, require_approval=is_private)
    rows = [
        [("📋 Book This Channel", f"adv:book:{ch_id}", "cd")],
        [("🚩 Report Channel", f"adv:report:{ch_id}", "cd")],
    ]
    if link:
        label = "🔗 Visit Channel (Require Approval)" if is_private else "🔗 Visit Channel"
        rows.insert(0, [(label, link, "url")])
    rows.append([("🔙 Back", "adv:browse", "cd")])
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb_url(rows))

async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ch_id = int(q.data.split(":")[2])
    context.user_data["report_channel_id"] = ch_id
    await q.edit_message_text(
        "🚩 <b>Report Channel</b>\n\nPlease describe the issue (spam, scam, adult content, etc.).\nSend your reason as the next message, or /cancel.",
        parse_mode="HTML", reply_markup=kb([back(f"adv:ch:{ch_id}")]))
    return REPORT_REASON

async def report_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch_id = context.user_data.pop("report_channel_id", None)
    if not ch_id:
        return ConversationHandler.END
    reason = (update.message.text or "").strip()[:500]
    if not reason:
        await update.message.reply_text("Reason cannot be empty. Try again.")
        context.user_data["report_channel_id"] = ch_id
        return REPORT_REASON
    await db.execute(
        "INSERT INTO channel_reports (channel_id, reporter_id, reason) VALUES ($1,$2,$3)",
        ch_id, update.effective_user.id, reason)
    c = await get_channel(ch_id)
    title = c["title"] if c else f"#{ch_id}"
    await update.message.reply_text(
        f"✅ Report submitted. Thank you — our admins will review {title}.",
        reply_markup=kb([back("adv:browse")]))
    try:
        await notify_superadmin(context.bot,
            f"🚩 <b>New channel report</b>\nChannel: {title} (<code>{ch_id}</code>)\n"
            f"Reporter: <code>{update.effective_user.id}</code>\nReason: {reason}")
    except Exception:
        pass
    return ConversationHandler.END

def build_report_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(report_start, pattern=r"^adv:report:\d+$")],
        states={REPORT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_finish)]},
        sha": "311c8dd0658759f372c9be9a2065c327fdb1a203",
        fallbacks=[CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern=r"^adv:ch:\d+$")],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

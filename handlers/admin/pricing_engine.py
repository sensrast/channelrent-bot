from telegram import Update
from telegram.ext import ContextTypes
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.queries.channels import list_all_listed, update_channel
from services.pricing_engine import compute_activity, compute_price_per_hour

@superadmin_only
async def pricing_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = ("⚙️ <b>Pricing Engine</b>\n\n"
           "Adjust price_per_1k_subs, price_per_100_views, multipliers in Settings panel.\n\n"
           "Run a full recalculation across all channels:")
    rows = [[("🔄 Recalculate All","admin:pricing:recalc")], back("admin:panel")]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

@superadmin_only
async def pricing_recalc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Recalculating...")
    rows = await list_all_listed()
    n = 0
    for c in rows:
        score, tier, eng = compute_activity(c["subscriber_count"], c["avg_views_24h"])
        price = compute_price_per_hour(c["subscriber_count"], c["avg_views_24h"], tier)
        await update_channel(c["channel_id"], activity_score=score, activity_tier=tier, engagement_rate=eng, base_price_credits=price, final_price_credits=price)
        n += 1
    await q.edit_message_text(f"✅ Recalculated {n} channels.", reply_markup=kb([back("admin:panel")]))

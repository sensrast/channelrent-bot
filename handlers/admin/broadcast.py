from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import asyncio, config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.queries.users import all_user_ids
from services.notification_service import notify

BCAST = 0

@superadmin_only
async def bcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("📢 Send the broadcast text:", reply_markup=kb([back("admin:panel")]))
    return BCAST

async def bcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    text = update.message.text
    ids = await all_user_ids()
    await update.message.reply_text(f"Sending to {len(ids)} users...")
    sent = 0
    for uid in ids:
        ok = await notify(update.get_bot(), uid, "broadcast", text)
        if ok: sent += 1
        await asyncio.sleep(0.03)
    await update.message.reply_text(f"✅ Delivered to {sent}/{len(ids)}.", reply_markup=kb([back("admin:panel")]))
    return ConversationHandler.END

def build_bcast_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(bcast_start, pattern=r"^admin:bcast$")],
        states={BCAST:[MessageHandler(filters.TEXT & ~filters.COMMAND, bcast_send)]},
        fallbacks=[],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
    )

from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.keyboards import kb, back
from utils.validators import is_upi, parse_int
from database.pool import db
from database.queries.users import get_user, set_upi
from services.payout_service import request_payout
from services.notification_service import notify_superadmin

PAYOUT_AMOUNT, PAYOUT_UPI, PAYOUT_NAME, PAYOUT_CONFIRM = range(4)

async def payout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = await get_user(q.from_user.id)
    min_p = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='min_payout_credits'") or 500)
    if user["earnings_pending"] < min_p:
        await q.edit_message_text(f"❌ Minimum payout is {min_p} cr. You have {user['earnings_pending']} cr pending.",
            reply_markup=kb([back("owner:earnings")]))
        return ConversationHandler.END
    context.user_data["payout"] = {"max": user["earnings_pending"], "min": min_p}
    await q.edit_message_text(f"💸 Enter credits to withdraw ({min_p}-{user['earnings_pending']}):")
    return PAYOUT_AMOUNT

async def payout_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = context.user_data.get("payout") or {}
    val = parse_int(update.message.text, p.get("min",500), p.get("max",0))
    if not val:
        await update.message.reply_text("Invalid amount. Try again.")
        return PAYOUT_AMOUNT
    p["credits"] = val
    await update.message.reply_text("Enter your UPI ID (e.g. yourname@bank):")
    return PAYOUT_UPI

async def payout_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upi = update.message.text.strip()
    if not is_upi(upi):
        await update.message.reply_text("Invalid UPI ID format. Try again.")
        return PAYOUT_UPI
    context.user_data["payout"]["upi"] = upi
    await update.message.reply_text("Enter UPI display name:")
    return PAYOUT_NAME

async def payout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = context.user_data["payout"]
    p["upi_name"] = update.message.text.strip()[:100]
    inr = p["credits"] // int(await db.fetchval("SELECT value FROM platform_settings WHERE key='credits_per_rupee'") or 1)
    p["inr"] = inr
    txt = (f"💸 <b>Payout Request</b>\n\nCredits: {p['credits']}\nINR: ₹{inr}\n"
           f"UPI: <code>{p['upi']}</code>\nName: {p['upi_name']}\n\nConfirm?")
    await update.message.reply_text(txt, parse_mode="HTML",
        reply_markup=kb([[("✅ Confirm","owner:payout:go"),("❌ Cancel","owner:payout:cancel")]]))
    return PAYOUT_CONFIRM

async def payout_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":cancel"):
        context.user_data.pop("payout", None)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("owner:earnings")]))
        return ConversationHandler.END
    p = context.user_data.pop("payout", None)
    if not p:
        await q.edit_message_text("Session expired.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    try:
        pid = await request_payout(q.from_user.id, p["credits"], p["inr"], p["upi"], p["upi_name"])
        await set_upi(q.from_user.id, p["upi"], p["upi_name"])
        await q.edit_message_text(f"✅ Payout requested! ID: <code>{pid}</code>\nProcessing in 1-24 hours.",
            parse_mode="HTML", reply_markup=kb([back("owner:earnings")]))
        await notify_superadmin(context.bot,
            f"💸 <b>New payout</b>\nUser: <code>{q.from_user.id}</code>\nAmount: ₹{p['inr']} ({p['credits']} cr)\nUPI: <code>{p['upi']}</code> ({p['upi_name']})\nPayout ID: <code>{pid}</code>")
    except ValueError as e:
        await q.edit_message_text(f"❌ {e}", reply_markup=kb([back("owner:earnings")]))
    return ConversationHandler.END

def build_payout_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(payout_start, pattern=r"^owner:payout$")],
        states={
            PAYOUT_AMOUNT:[MessageHandler(filters.TEXT & ~filters.COMMAND, payout_amount)],
            PAYOUT_UPI:[MessageHandler(filters.TEXT & ~filters.COMMAND, payout_upi)],
            PAYOUT_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, payout_name)],
            PAYOUT_CONFIRM:[CallbackQueryHandler(payout_confirm, pattern=r"^owner:payout:(go|cancel)$")],
        },
        fallbacks=[_CmdHandler("cancel", _univ_cancel)],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
import config
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from utils.keyboards import kb, back
from utils.formatters import fmt_credits
from utils.validators import parse_int
from handlers.common.wallet_common import wallet_card
from database.queries.users import get_user
from database.queries.credits import adjust_credits, list_transactions
from database.pool import db
from services.notification_service import notify_superadmin

TOPUP_AMOUNT, TOPUP_SCREENSHOT = range(2)

async def wallet_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = await get_user(q.from_user.id)
    txt = wallet_card(user)
    rows = [[("➕ Top Up","adv:topup")],[("📜 Transactions","adv:txns")], back("home")]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def txn_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_transactions(q.from_user.id, 15)
    if not rows:
        body = "No transactions yet."
    else:
        body = ""
        for r in rows:
            sign = "+" if r["amount"] >= 0 else ""
            body += f"{r['created_at']:%Y-%m-%d %H:%M} • {r['type']} • {sign}{r['amount']}\n"
    await q.edit_message_text(f"📜 <b>Transaction History</b>\n\n{body}", parse_mode="HTML", reply_markup=kb([back("adv:wallet")]))

async def topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    min_t = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='min_topup_credits'") or 100)
    txt = (f"💰 <b>Top Up Credits</b>\n\nRate: ₹1 = 1 credit\nMinimum: {min_t} credits\n\nChoose amount or enter custom:")
    rows = [
        [("100 cr — ₹100","adv:topup:amt:100"),("200 cr — ₹200","adv:topup:amt:200")],
        [("500 cr — ₹500","adv:topup:amt:500"),("1000 cr — ₹1000","adv:topup:amt:1000")],
        [("2000 cr — ₹2000","adv:topup:amt:2000"),("5000 cr — ₹5000","adv:topup:amt:5000")],
        [("✏️ Custom Amount","adv:topup:custom")],
        back("adv:wallet"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return ConversationHandler.END

async def topup_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "adv:topup:custom":
        min_t = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='min_topup_credits'") or 100)
        max_t = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='max_topup_credits'") or 100000)
        context.user_data["topup_min"] = min_t
        context.user_data["topup_max"] = max_t
        await q.edit_message_text(f"✏️ Enter custom amount in credits (minimum {min_t}):", reply_markup=kb([back("adv:topup")]))
        return TOPUP_AMOUNT
    amt = int(data.rsplit(":",1)[1])
    context.user_data["topup_amount"] = amt
    return await _show_pay(q, context, amt)

async def topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    min_t = int(context.user_data.get("topup_min") or await db.fetchval("SELECT value FROM platform_settings WHERE key='min_topup_credits'") or 100)
    max_t = int(context.user_data.get("topup_max") or await db.fetchval("SELECT value FROM platform_settings WHERE key='max_topup_credits'") or 100000)
    val = parse_int(update.message.text, min_t, max_t)
    if not val:
        await update.message.reply_text(f"Invalid amount. Enter a number between {min_t} and {max_t}.")
        return TOPUP_AMOUNT
    context.user_data["topup_amount"] = val
    return await _show_pay(update.message, context, val)

async def _show_pay(target, context, amt):
    txt = (f"💳 <b>Payment Instructions</b>\n\n"
           f"Amount: ₹{amt}\nCredits: {amt}\n\n"
           f"━━━ Pay via UPI ━━━\n"
           f"📱 UPI: <code>{config.UPI_ID}</code>\n"
           f"👤 Name: {config.UPI_NAME}\n"
           f"💵 Amount: ₹{amt}\n\n"
           f"After paying, send a screenshot of the payment as the next message.\n"
           f"Credits will be added within 30 minutes.")
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(txt, parse_mode="HTML", reply_markup=kb([[("❌ Cancel","adv:wallet")]]))
    else:
        await target.reply_text(txt, parse_mode="HTML", reply_markup=kb([[("❌ Cancel","adv:wallet")]]))
    return TOPUP_SCREENSHOT

async def topup_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.photo:
        await msg.reply_text("Please send a screenshot photo of the payment.")
        return TOPUP_SCREENSHOT
    amt = context.user_data.get("topup_amount")
    if not amt:
        await msg.reply_text("Session expired. /start over.")
        return ConversationHandler.END
    file_id = msg.photo[-1].file_id
    async with db.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT credits_balance FROM users WHERE user_id=$1 FOR UPDATE", msg.from_user.id)
            bal = row["credits_balance"] if row else 0
            tx_id = await conn.fetchval("""INSERT INTO credit_transactions
                (user_id,type,amount,balance_before,balance_after,description,payment_method,payment_screenshot_file_id,payment_amount_inr,payment_verified)
                VALUES ($1,'topup_upi',0,$2,$2,$3,'UPI',$4,$5,FALSE) RETURNING transaction_id""",
                msg.from_user.id, bal, f"UPI top-up pending ₹{amt}", file_id, amt)
    await msg.reply_text(f"✅ Payment received!\nReference: TXN-{tx_id}\nWe'll verify within 30 minutes.\n\nTap /start to return to menu.")
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    review_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"admin:topup:ok:{tx_id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"admin:topup:no:{tx_id}"),
    ]])
    caption = (f"💳 <b>New Top-up</b>\n"
               f"User: {msg.from_user.full_name} (<code>{msg.from_user.id}</code>)\n"
               f"Amount: ₹{amt}\nTXN: <code>{tx_id}</code>")
    for sid in config.SUPERADMIN_IDS:
        try:
            await context.bot.send_photo(sid, file_id, caption=caption, parse_mode="HTML", reply_markup=review_kb)
        except Exception:
            try:
                await context.bot.send_message(sid, caption + "\n\n(screenshot unavailable)",
                    parse_mode="HTML", reply_markup=review_kb)
            except Exception:
                pass
    context.user_data.clear()
    return ConversationHandler.END

def build_topup_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(topup_pick, pattern=r"^adv:topup:(amt:\d+|custom)$")],
        states={
            TOPUP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_amount)],
            TOPUP_SCREENSHOT: [MessageHandler(filters.PHOTO, topup_screenshot)],
        },
        fallbacks=[CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern=r"^adv:wallet$")],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

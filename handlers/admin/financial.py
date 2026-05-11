from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.queries.credits import list_pending_topups, get_transaction, mark_payment_verified, adjust_credits
from database.queries.payouts import list_pending, get_payout
from services.payout_service import complete_payout, reject_payout
from services.notification_service import notify
from database.pool import db

PAYOUT_REF, REJECT_REASON = range(2)

@superadmin_only
async def finance_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("💰 <b>Financial Panel</b>", parse_mode="HTML", reply_markup=kb([
        [("💳 Pending Top-ups","admin:topups"),("💸 Pending Payouts","admin:payouts")],
        back("admin:panel"),
    ]))

@superadmin_only
async def topup_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_pending_topups()
    if not rows:
        await q.edit_message_text("✅ No pending top-ups.", reply_markup=kb([back("admin:panel")]))
        return
    txt = "💳 <b>Pending Top-ups</b>\n"
    kb_rows = []
    for r in rows[:10]:
        txt += f"\n• TXN-{r['transaction_id']} • user {r['user_id']} • ₹{r['payment_amount_inr']}"
        kb_rows.append([(f"Review TXN-{r['transaction_id']}", f"admin:topup:{r['transaction_id']}")])
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def topup_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tx_id = int(q.data.split(":")[2])
    t = await get_transaction(tx_id)
    if not t:
        await q.edit_message_text("Not found.", reply_markup=kb([back("admin:topups")]))
        return
    txt = (f"TXN-{tx_id}\nUser: <code>{t['user_id']}</code>\nAmount: ₹{t['payment_amount_inr']}\n"
           f"Verified: {t['payment_verified']}")
    rows = [[("✅ Approve",f"admin:topup:ok:{tx_id}"),("❌ Reject",f"admin:topup:no:{tx_id}")], back("admin:topups")]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

@superadmin_only
async def topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Approving...")
    tx_id = int(q.data.split(":")[3])
    t = await get_transaction(tx_id)
    if not t or t["payment_verified"]:
        await q.edit_message_text("Already processed.", reply_markup=kb([back("admin:topups")]))
        return
    amt = t["payment_amount_inr"]
    async with db.acquire() as conn:
        async with conn.transaction():
            await adjust_credits(conn, t["user_id"], amt, "topup_manual",
                description=f"Approved TXN-{tx_id}", created_by=q.from_user.id)
            await mark_payment_verified(tx_id, q.from_user.id)
    await q.edit_message_text(f"✅ Approved TXN-{tx_id}: +{amt} cr.", reply_markup=kb([back("admin:topups")]))
    await notify(context.bot, t["user_id"], "topup_done",
        f"✅ <b>Top-up successful!</b>\n+{amt} credits added.\nTXN-{tx_id}")

@superadmin_only
async def topup_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tx_id = int(q.data.split(":")[3])
    t = await get_transaction(tx_id)
    if not t or t["payment_verified"]: return
    await db.execute("UPDATE credit_transactions SET payment_verified=TRUE, description=COALESCE(description,'')||' [REJECTED]' WHERE transaction_id=$1", tx_id)
    await q.edit_message_text(f"❌ Rejected TXN-{tx_id}.", reply_markup=kb([back("admin:topups")]))
    await notify(context.bot, t["user_id"], "topup_rejected",
        f"❌ Top-up TXN-{tx_id} rejected. Contact @{config.SUPPORT_USERNAME} if this is a mistake.")

@superadmin_only
async def payout_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_pending()
    if not rows:
        await q.edit_message_text("✅ No pending payouts.", reply_markup=kb([back("admin:panel")]))
        return
    txt = "💸 <b>Pending Payouts</b>\n"
    kb_rows = []
    for r in rows[:10]:
        txt += f"\n• #{r['payout_id']} • user {r['owner_id']} • ₹{r['inr_amount']} • {r['upi_id']}"
        kb_rows.append([(f"Process #{r['payout_id']}", f"admin:payout:{r['payout_id']}")])
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def payout_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = int(q.data.split(":")[2])
    p = await get_payout(pid)
    if not p:
        await q.edit_message_text("Not found.", reply_markup=kb([back("admin:payouts")]))
        return
    txt = (f"💸 Payout #{pid}\nUser: <code>{p['owner_id']}</code>\n₹{p['inr_amount']} ({p['credits_requested']} cr)\n"
           f"UPI: <code>{p['upi_id']}</code> ({p['upi_name']})\nStatus: {p['status']}")
    rows = [[("✅ Mark Paid (enter ref)",f"admin:payout:ok:{pid}"),("❌ Reject",f"admin:payout:no:{pid}")], back("admin:payouts")]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def payout_ok_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    pid = int(q.data.split(":")[3])
    context.user_data["payout_pid"] = pid
    await q.edit_message_text("Enter UPI transaction reference:")
    return PAYOUT_REF

async def payout_ok_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    pid = context.user_data.pop("payout_pid", None)
    ref = update.message.text.strip()[:200]
    p = await complete_payout(pid, update.effective_user.id, ref)
    if not p:
        await update.message.reply_text("Already processed.")
        return ConversationHandler.END
    await update.message.reply_text(f"✅ Marked paid. Ref: {ref}", reply_markup=kb([back("admin:payouts")]))
    await notify(update.get_bot(), p["owner_id"], "payout_done",
        f"✅ <b>Payout sent!</b>\n₹{p['inr_amount']} to <code>{p['upi_id']}</code>\nRef: <code>{ref}</code>")
    return ConversationHandler.END

async def payout_no_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    pid = int(q.data.split(":")[3])
    context.user_data["payout_no_pid"] = pid
    await q.edit_message_text("Enter rejection reason:")
    return REJECT_REASON

async def payout_no_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    pid = context.user_data.pop("payout_no_pid", None)
    reason = update.message.text.strip()[:300]
    p = await reject_payout(pid, update.effective_user.id, reason)
    if not p:
        await update.message.reply_text("Already processed.")
        return ConversationHandler.END
    await update.message.reply_text("❌ Rejected & refunded to pending earnings.", reply_markup=kb([back("admin:payouts")]))
    await notify(update.get_bot(), p["owner_id"], "payout_rejected",
        f"❌ Payout #{pid} rejected.\nReason: {reason}\nCredits returned to pending earnings.")
    return ConversationHandler.END

def build_payout_admin_conv():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(payout_ok_start, pattern=r"^admin:payout:ok:\d+$"),
            CallbackQueryHandler(payout_no_start, pattern=r"^admin:payout:no:\d+$"),
        ],
        states={
            PAYOUT_REF:[MessageHandler(filters.TEXT & ~filters.COMMAND, payout_ok_finish)],
            REJECT_REASON:[MessageHandler(filters.TEXT & ~filters.COMMAND, payout_no_finish)],
        },
        fallbacks=[],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
    )

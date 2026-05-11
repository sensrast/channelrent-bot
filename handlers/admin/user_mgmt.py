from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from utils.formatters import fmt_credits
from database.queries.users import get_user, search_users, set_banned
from database.queries.credits import adjust_credits
from database.pool import db

SEARCH, CRED_AMT = range(2)

@superadmin_only
async def users_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    total = await db.fetchval("SELECT COUNT(*) FROM users") or 0
    await q.edit_message_text(f"👥 <b>Users</b>\n\nTotal: {total}",
        parse_mode="HTML", reply_markup=kb([[("🔍 Search User","admin:user:search")], back("admin:panel")]))

async def user_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    await q.edit_message_text("Enter user ID or username:")
    return SEARCH

async def user_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    rows = await search_users(update.message.text.strip(), limit=5)
    if not rows:
        await update.message.reply_text("No users found.", reply_markup=kb([back("admin:users")]))
        return ConversationHandler.END
    kb_rows = [[(f"{r['first_name'] or r['user_id']}", f"admin:user:{r['user_id']}")] for r in rows]
    kb_rows.append(back("admin:users"))
    await update.message.reply_text("Pick:", reply_markup=kb(kb_rows))
    return ConversationHandler.END

@superadmin_only
async def user_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.split(":")[2])
    u = await get_user(uid)
    if not u:
        await q.edit_message_text("Not found.", reply_markup=kb([back("admin:users")]))
        return
    txt = (f"👤 <b>{u['first_name'] or '-'} @{u['username'] or '-'}</b>\nID: <code>{u['user_id']}</code>\n"
           f"Banned: {u['is_banned']}\n💰 Balance: {fmt_credits(u['credits_balance'])}\n"
           f"📈 Purchased: {fmt_credits(u['credits_total_purchased'])} • Spent: {fmt_credits(u['credits_total_spent'])}\n"
           f"⏳ Earnings pending: {fmt_credits(u['earnings_pending'])} • Paid: {fmt_credits(u['earnings_paid'])}")
    rows = [
        [("➕ Add Credits", f"admin:user:add:{uid}"),("➖ Remove Credits", f"admin:user:sub:{uid}")],
        [("🚫 Ban" if not u["is_banned"] else "✅ Unban", f"admin:user:ban:{uid}")],
        back("admin:users"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def cred_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    parts = q.data.split(":")
    action, uid = parts[2], int(parts[3])
    context.user_data["cred"] = {"action": action, "uid": uid}
    await q.edit_message_text(f"Enter credits to {'ADD' if action=='add' else 'REMOVE'}:")
    return CRED_AMT

async def cred_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    d = context.user_data.pop("cred", None)
    if not d: return ConversationHandler.END
    try:
        amt = int(update.message.text.strip())
    except Exception:
        await update.message.reply_text("Invalid number.")
        return ConversationHandler.END
    delta = amt if d["action"] == "add" else -amt
    try:
        async with db.acquire() as conn:
            async with conn.transaction():
                await adjust_credits(conn, d["uid"], delta,
                    "topup_manual" if delta>0 else "penalty",
                    description=f"Admin {d['action']} by {update.effective_user.id}",
                    created_by=update.effective_user.id)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return ConversationHandler.END
    await update.message.reply_text(f"✅ {('Added' if delta>0 else 'Removed')} {abs(delta)} cr.")
    return ConversationHandler.END

@superadmin_only
async def user_ban_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.split(":")[3])
    u = await get_user(uid)
    if not u: return
    await set_banned(uid, not u["is_banned"], "Banned by admin" if not u["is_banned"] else None)
    q.data = f"admin:user:{uid}"
    await user_view(update, context)

def build_user_admin_conv():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_search_start, pattern=r"^admin:user:search$"),
            CallbackQueryHandler(cred_start, pattern=r"^admin:user:(add|sub):\d+$"),
        ],
        states={
            SEARCH:[MessageHandler(filters.TEXT & ~filters.COMMAND, user_search_do)],
            CRED_AMT:[MessageHandler(filters.TEXT & ~filters.COMMAND, cred_finish)],
        },
        fallbacks=[_CmdHandler("cancel", _univ_cancel)],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

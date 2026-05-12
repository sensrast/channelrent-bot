from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, kb_url, back
from utils.formatters import fmt_credits
from database.queries.users import get_user, search_users, set_banned, list_users
from database.queries.credits import adjust_credits
from database.pool import db

SEARCH, CRED_AMT = range(2)

@superadmin_only
async def users_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    total = await db.fetchval("SELECT COUNT(*) FROM users") or 0
    page = 0
    data = q.data or ""
    if data.startswith("admin:users:p:"):
        try: page = int(data.split(":")[3])
        except: page = 0
    per_page = 10
    rows = await list_users(limit=per_page, offset=page*per_page)
    kb_rows = []
    for r in rows:
        label = f"{r['first_name'] or r['username'] or r['user_id']}" + (" 🚫" if r['is_banned'] else "")
        kb_rows.append([(label, f"admin:user:{r['user_id']}")])
    nav = []
    if page > 0: nav.append(("◀️ Prev", f"admin:users:p:{page-1}"))
    if (page+1)*per_page < total: nav.append(("Next ▶️", f"admin:users:p:{page+1}"))
    if nav: kb_rows.append(nav)
    kb_rows.append([("🔍 Search","admin:users:search")])
    kb_rows.append([back("admin:panel")])
    await q.edit_message_text(
        f"👤 <b>User Management</b> — {total} total - Page {page+1}",
        parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def user_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Send username, user ID or name to search:", reply_markup=kb([back("admin:users")]))
    return SEARCH

@superadmin_only
async def user_search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    res = await search_users(q, 20)
    if not res:
        await update.message.reply_text("No users found.")
        return ConversationHandler.END
    rows = []
    for r in res:
        label = f"{r['first_name'] or r['username'] or r['user_id']}" + (" 🚫" if r['is_banned'] else "")
        rows.append([(label, f"admin:user:{r['user_id']}")])
    rows.append([back("admin:users")])
    await update.message.reply_text("🔍 Results", reply_markup=kb(rows))
    return ConversationHandler.END

@superadmin_only
async def user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.split(":")[2])
    u = await get_user(uid)
    if not u:
        await q.edit_message_text("Not found.", reply_markup=kb([back("admin:users")]))
        return
    detail = (f"👤 <b>{u['first_name'] or '-'}}</b>\n"
              f"ID: <code>{u['user_id']}</code>\n"
              f"Username: @{u['username'] or '-'}\n"
              f"Credits: {fmt_credits(u['credits_balance'])}\n"
              f"Total purchased: {fmt_credits(u['credits_total_purchased'])}\n"
              f"Referred by: {u['referred_by'] or '-'}\n"
              f"Status: {'🚫 Banned' if u['is_banned'] else '✅ Active'}\n")
    username = u['username']
    if username:
        rows = [[ ("💢 DM User", f"https://t.me/{username}", "url") ]]
    else:
        rows = [[ ("💢 DM User (open)", f"tg://user?id={uid}", "url") ]]
    rows += [
        [("💰 Adjust Credits", f"admin:user:adj:{uid}")],
        [("🚫 Ban" if not u['is_banned'] else "✅ Unban", f"admin:user:ban:{uid}:{0 if u['is_banned'] else 1}")],
        [back("admin:users")],
    ]
    from utils.keyboards import kb_url
    await q.edit_message_text(detail, parse_mode="HTML", reply_markup=kb_url(rows))

@superadmin_only
async def adjust_credits_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.split(":")[3])
    context.user_data['admin_adj_uid'] = uid
    await q.edit_message_text(f"Amount for {uid} (positive add, negative deduct):", reply_markup=kb([back("admin:user")]))
    return CRED_AMT

@superadmin_only
async def adjust_credits_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if 'admin_adj_uid' not in context.user_data:
        await msg.reply_text("Session expired."); return ConversationHandler.END
    uid = context.user_data.pop('admin_adj_uid')
    try:
        amt = int(msg.text.strip())
    except:
        await msg.reply_text("Invalid number.")
        return ConversationHandler.END
    async with db.acquire() as conn:
        async with conn.transaction():
            await adjust_credits(conn, uid, amt, 'admin_adjustment', description='Manual admin adjustment')
    await msg.reply_text(f"Adjusted {uid} by {amt}.")
    return ConversationHandler.END

@superadmin_only
async def ban_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data.split(":")
    uid = int(data[2]); ban = data[3] == "1"
    await set_banned(uid, ban)
    await q.edit_message_text("🚯 Updated.", reply_markup=kb([back("admin:user")]))

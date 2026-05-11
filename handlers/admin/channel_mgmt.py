from telegram import Update
from telegram.ext import ContextTypes
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.queries.channels import list_all_verified, update_channel, get_channel

@superadmin_only
async def channels_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await list_all_verified()
    txt = f"📢 <b>All Channels</b> ({len(rows)})\n"
    kb_rows = []
    for c in rows[:15]:
        txt += f"\n• {c['title']} • {'🟢' if c['is_listed'] and not c['is_suspended'] else '🔴'}"
        kb_rows.append([(f"⚙️ {c['title'][:25]}", f"admin:ch:{c['channel_id']}")])
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def channel_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[2])
    c = await get_channel(cid)
    if not c:
        await q.edit_message_text("Not found.", reply_markup=kb([back("admin:channels")]))
        return
    txt = (f"📢 <b>{c['title']}</b>\nOwner: <code>{c['owner_id']}</code>\n"
           f"Subs: {c['subscriber_count']:,} • {c['final_price_credits']} cr/hr\n"
           f"Listed: {c['is_listed']} • Suspended: {c['is_suspended']}")
    rows = [
        [("🔴 Suspend" if not c["is_suspended"] else "✅ Unsuspend", f"admin:ch:sus:{cid}")],
        back("admin:channels"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

@superadmin_only
async def channel_suspend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Toggled")
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c: return
    await update_channel(cid, is_suspended=not c["is_suspended"], suspension_reason="Admin action")
    q.data = f"admin:ch:{cid}"
    await channel_view(update, context)

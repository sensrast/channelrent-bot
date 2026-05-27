from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.pool import db
from database.queries.channels import update_channel

PAGE_SIZE = 10

async def _list_channels():
    return await db.fetch(
        "SELECT channel_id, telegram_chat_id, title, COALESCE(auto_accept_requests,FALSE) AS aar "
        "FROM channels WHERE is_active=TRUE ORDER BY title ASC NULLS LAST"
    )

def _parse_page(data):
    parts = data.split(":")
    if len(parts) >= 4 and parts[2] == "p":
        try:
            return max(0, int(parts[3]))
        except Exception:
            return 0
    return 0

async def _render(q, page, context):
    rows = await _list_channels()
    total = len(rows)
    if total == 0:
        await q.edit_message_text(
            "🤖 <b>Auto Accept Requests</b>\n\nNo channels found. Add the bot as admin to a channel and list it first.",
            parse_mode="HTML",
            reply_markup=kb([back("admin:panel")]),
        )
        return
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    chunk = rows[start:start + PAGE_SIZE]
    enabled_count = sum(1 for r in rows if r["aar"])
    txt = (
        "🤖 <b>Auto Accept Requests</b>\n\n"
        "Toggle per-channel auto-accept for join requests.\n"
        f"Enabled: <b>{enabled_count}</b> / {total}\n\n"
        "Tap a channel to toggle ON/OFF."
    )
    kb_rows = []
    for c in chunk:
        mark = "✅" if c["aar"] else "⬜"
        title = (c["title"] or f"chat {c['telegram_chat_id']}")[:40]
        kb_rows.append([(f"{mark} {title}", f"admin:aar:t:{c['channel_id']}:{page}")])
    nav = []
    if page > 0:
        nav.append(("◀️ Prev", f"admin:aar:p:{page-1}"))
    nav.append((f"Page {page+1}/{pages}", "noop"))
    if page < pages - 1:
        nav.append(("Next ▶️", f"admin:aar:p:{page+1}"))
    kb_rows.append(nav)
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def autoaccept_panel(update, context):
    q = update.callback_query
    await q.answer()
    page = _parse_page(q.data or "")
    await _render(q, page, context)

@superadmin_only
async def autoaccept_toggle(update, context):
    q = update.callback_query
    parts = (q.data or "").split(":")
    try:
        cid = int(parts[3])
        page = int(parts[4]) if len(parts) > 4 else 0
    except (ValueError, IndexError):
        await q.answer("Bad data", show_alert=True)
        return
    row = await db.fetchrow(
        "SELECT channel_id, telegram_chat_id, title, COALESCE(auto_accept_requests,FALSE) AS aar "
        "FROM channels WHERE channel_id=$1",
        cid,
    )
    if not row:
        await q.answer("Channel not found", show_alert=True)
        return
    new_val = not row["aar"]
    if new_val:
        try:
            me = await context.bot.get_me()
            member = await context.bot.get_chat_member(chat_id=row["telegram_chat_id"], user_id=me.id)
            status = getattr(member, "status", "")
            if status not in ("administrator", "creator"):
                await q.answer("⚠️ Bot is not admin in this channel.", show_alert=True)
                return
        except TelegramError as e:
            await q.answer(f"⚠️ Cannot verify admin: {e}", show_alert=True)
            return
    await update_channel(cid, auto_accept_requests=new_val)
    await q.answer(("✅ Enabled" if new_val else "⬜ Disabled") + f" for {row['title'] or cid}")
    await _render(q, page, context)

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.keyboards import kb, back
from utils.validators import parse_int
from utils.formatters import activity_emoji
from services.pricing_engine import clamp_owner_price
from database.queries.channels import get_channel, update_channel, list_all_categories

log = logging.getLogger(__name__)

EDIT_ALLOWED, EDIT_FORBIDDEN, EDIT_PRICE = range(3)


async def channel_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        await q.edit_message_text("Not found.", reply_markup=kb([back("owner:channels")]))
        return
    apv_label = "Auto" if c["auto_approve"] else "Manual"
    cat_name = f"{c.get('category_emoji') or ''} {c.get('category_name') or 'Not set'}".strip()
    txt = (f"⚙️ <b>Edit: {c['title']}</b>\n\n"
           f"📂 Category: {cat_name}\n"
           f"💰 Price: <b>{c['final_price_credits']} cr/hr</b>\n"
           f"🔐 Approval: <b>{apv_label}</b>\n\n"
           f"✅ Allowed: {c['allowed_content'] or '—'}\n"
           f"❌ Forbidden: {c['forbidden_content'] or '—'}")
    rows = [
        [("📂 Change Category", f"owner:ch:editcat:{cid}")],
        [("💰 Change Price", f"owner:ch:editprice:{cid}")],
        [(f"🔐 Approval: {apv_label} (toggle)", f"owner:ch:toggleapv:{cid}")],
        [("✅ Edit Allowed Content", f"owner:ch:editallowed:{cid}")],
        [("❌ Edit Forbidden Content", f"owner:ch:editforbidden:{cid}")],
        back(f"owner:ch:{cid}"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))


async def channel_edit_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return
    cats = await list_all_categories()
    rows, cur = [], []
    for cat in cats:
        cur.append((f"{cat['emoji']} {cat['name']}", f"owner:ch:setcat:{cid}:{cat['category_id']}"))
        if len(cur) == 2:
            rows.append(cur); cur = []
    if cur:
        rows.append(cur)
    rows.append(back(f"owner:ch:edit:{cid}"))
    await q.edit_message_text("📂 Pick a new category:", reply_markup=kb(rows))


async def channel_set_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Updated")
    parts = q.data.split(":")
    cid = int(parts[3]); cat_id = int(parts[4])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return
    await update_channel(cid, category_id=cat_id)
    q.data = f"owner:ch:edit:{cid}"
    await channel_edit_menu(update, context)


async def channel_toggle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Toggled")
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return
    new_auto = not c["auto_approve"]
    await update_channel(cid, auto_approve=new_auto, requires_approval=not new_auto)
    q.data = f"owner:ch:edit:{cid}"
    await channel_edit_menu(update, context)


async def channel_edit_allowed_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return ConversationHandler.END
    context.user_data["edit_ch_id"] = cid
    await q.edit_message_text(
        f"✏️ Send the new ALLOWED content description (max 500 chars).\n\n"
        f"Current: {c['allowed_content'] or '—'}\n\n/cancel to abort.")
    return EDIT_ALLOWED


async def channel_edit_allowed_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = context.user_data.get("edit_ch_id")
    if not cid:
        return ConversationHandler.END
    c = await get_channel(cid)
    if not c or c["owner_id"] != update.effective_user.id:
        return ConversationHandler.END
    await update_channel(cid, allowed_content=update.message.text[:500])
    await update.message.reply_text("✅ Allowed content updated.", reply_markup=kb([
        [("⚙️ Back to Edit", f"owner:ch:edit:{cid}")], back(f"owner:ch:{cid}")]))
    context.user_data.pop("edit_ch_id", None)
    return ConversationHandler.END


async def channel_edit_forbidden_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return ConversationHandler.END
    context.user_data["edit_ch_id"] = cid
    await q.edit_message_text(
        f"✏️ Send the new FORBIDDEN content description (max 500 chars).\n\n"
        f"Current: {c['forbidden_content'] or '—'}\n\n/cancel to abort.")
    return EDIT_FORBIDDEN


async def channel_edit_forbidden_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = context.user_data.get("edit_ch_id")
    if not cid:
        return ConversationHandler.END
    c = await get_channel(cid)
    if not c or c["owner_id"] != update.effective_user.id:
        return ConversationHandler.END
    await update_channel(cid, forbidden_content=update.message.text[:500])
    await update.message.reply_text("✅ Forbidden content updated.", reply_markup=kb([
        [("⚙️ Back to Edit", f"owner:ch:edit:{cid}")], back(f"owner:ch:{cid}")]))
    context.user_data.pop("edit_ch_id", None)
    return ConversationHandler.END


async def channel_edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[3])
    c = await get_channel(cid)
    if not c or c["owner_id"] != q.from_user.id:
        return ConversationHandler.END
    sp = c["base_price_credits"] or c["final_price_credits"]
    lo = max(config.MIN_LISTING_PRICE, int(sp * 0.5))
    hi = min(config.MAX_LISTING_PRICE, int(sp * 1.5))
    context.user_data["edit_ch_id"] = cid
    context.user_data["edit_ch_sp"] = sp
    await q.edit_message_text(
        f"💰 Current price: <b>{c['final_price_credits']} cr/hr</b>\n"
        f"Suggested (base): {sp} cr/hr\n\n"
        f"Enter a new price between <b>{lo}</b> and <b>{hi}</b> cr/hr (±50% of base).\n\n/cancel to abort.",
        parse_mode="HTML")
    return EDIT_PRICE


async def channel_edit_price_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = context.user_data.get("edit_ch_id")
    sp = context.user_data.get("edit_ch_sp")
    if not cid or not sp:
        return ConversationHandler.END
    c = await get_channel(cid)
    if not c or c["owner_id"] != update.effective_user.id:
        return ConversationHandler.END
    val = parse_int(update.message.text)
    if not val:
        await update.message.reply_text("Invalid. Enter a number.")
        return EDIT_PRICE
    final = clamp_owner_price(sp, val)
    await update_channel(cid, final_price_credits=final, price_per_hour_credits=final, owner_custom_price=val)
    await update.message.reply_text(
        f"✅ Price updated to <b>{final} cr/hr</b>.", parse_mode="HTML",
        reply_markup=kb([[("⚙️ Back to Edit", f"owner:ch:edit:{cid}")], back(f"owner:ch:{cid}")]))
    context.user_data.pop("edit_ch_id", None)
    context.user_data.pop("edit_ch_sp", None)
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("edit_ch_id", None)
    context.user_data.pop("edit_ch_sp", None)
    if update.message:
        await update.message.reply_text("❌ Cancelled.", reply_markup=kb([back("owner:channels")]))
    return ConversationHandler.END


def build_channel_edit_conv():
    from telegram.ext import CommandHandler
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(channel_edit_allowed_start, pattern=r"^owner:ch:editallowed:\d+$"),
            CallbackQueryHandler(channel_edit_forbidden_start, pattern=r"^owner:ch:editforbidden:\d+$"),
            CallbackQueryHandler(channel_edit_price_start, pattern=r"^owner:ch:editprice:\d+$"),
        ],
        states={
            EDIT_ALLOWED: [MessageHandler(filters.TEXT & ~filters.COMMAND, channel_edit_allowed_save)],
            EDIT_FORBIDDEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, channel_edit_forbidden_save)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, channel_edit_price_save)],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern=r"^(home|owner:channels|owner:ch:\d+|owner:ch:edit:\d+)$"),
        ],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

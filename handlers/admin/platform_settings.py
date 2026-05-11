from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.pool import db

BOOL_KEYS = {"marketplace_enabled","maintenance_mode","watermark_enabled"}

def _is_truthy(v):
    return str(v).strip().lower() in ("1","true","yes","on","t","y")


EDIT = 0

KEYS = [
    "platform_commission_percent","min_topup_credits","max_topup_credits","min_payout_credits",
    "credits_per_rupee","min_booking_hours","max_booking_hours","max_channels_per_owner",
    "max_active_bookings_per_advertiser","referral_bonus_credits","new_user_bonus_credits",
    "marketplace_enabled","maintenance_mode","maintenance_message","watermark_enabled",
]

@superadmin_only
async def settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await db.fetch("SELECT key, value FROM platform_settings WHERE key=ANY($1::text[])", KEYS)
    vals = {r["key"]: r["value"] for r in rows}
    txt = "🔧 <b>Platform Settings</b>\n"
    kb_rows = []
    for k in KEYS:
        cur = vals.get(k, "?")
        if k in BOOL_KEYS:
            on = _is_truthy(cur)
            label = f"{'🟢 ON' if on else '🔴 OFF'} — {k}"
            txt += f"\n• <b>{k}</b>: <code>{'ON' if on else 'OFF'}</code>"
            kb_rows.append([(label, f"admin:tog:{k}")])
        else:
            txt += f"\n• <b>{k}</b>: <code>{cur}</code>"
            kb_rows.append([(f"✏️ {k}", f"admin:set:{k}")])
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.split(":", 2)[2]
    if key not in BOOL_KEYS:
        await q.answer("Not a toggle", show_alert=True); return
    cur = await db.fetchval("SELECT value FROM platform_settings WHERE key=$1", key)
    new_val = "false" if _is_truthy(cur) else "true"
    await db.execute("UPDATE platform_settings SET value=$2, updated_at=NOW(), updated_by=$3 WHERE key=$1", key, new_val, q.from_user.id)
    await settings_panel(update, context)


async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    key = q.data.split(":",2)[2]
    if key not in KEYS:
        await q.answer("Bad key", show_alert=True); return ConversationHandler.END
    context.user_data["set_key"] = key
    cur = await db.fetchval("SELECT value FROM platform_settings WHERE key=$1", key)
    await q.edit_message_text(f"Current <b>{key}</b>: <code>{cur}</code>\n\nSend new value:",
        parse_mode="HTML", reply_markup=kb([back("admin:settings")]))
    return EDIT

async def set_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    key = context.user_data.pop("set_key", None)
    if not key: return ConversationHandler.END
    val = update.message.text.strip()
    await db.execute("UPDATE platform_settings SET value=$2, updated_at=NOW(), updated_by=$3 WHERE key=$1", key, val, update.effective_user.id)
    await update.message.reply_text(f"✅ <b>{key}</b> = <code>{val}</code>", parse_mode="HTML",
        reply_markup=kb([back("admin:settings")]))
    return ConversationHandler.END

def build_settings_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(set_start, pattern=r"^admin:set:[a-z_]+$")],
        states={EDIT:[MessageHandler(filters.TEXT & ~filters.COMMAND, set_finish)]},
        fallbacks=[_CmdHandler("cancel", _univ_cancel)],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

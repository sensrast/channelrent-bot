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

BOOL_KEYS = {"marketplace_enabled","maintenance_mode","watermark_enabled","force_sub_enabled"}

def _is_truthy(v):
    return str(v).strip().lower() in ("1","true","yes","on","t","y")

EDIT = 0

GENERAL_KEYS = [
    "platform_commission_percent","min_topup_credits","max_topup_credits","min_payout_credits",
    "credits_per_rupee","min_booking_hours","max_booking_hours","max_channels_per_owner",
    "max_active_bookings_per_advertiser","referral_bonus_credits","new_user_bonus_credits",
    "min_subscriber_count","inactive_days_remove",
    "marketplace_enabled","maintenance_mode","maintenance_message",
    "watermark_enabled","watermark_text",
    "force_sub_enabled","force_sub_channel",
]

PRICE_KEYS = [
    "base_price_per_post_credits","price_per_1k_subscribers","price_per_100_views",
    "activity_multiplier_high","activity_multiplier_medium","activity_multiplier_low",
    "min_listing_price","max_listing_price",
]

KEYS = GENERAL_KEYS + PRICE_KEYS

@superadmin_only
async def settings_panel(update, context):
    q = update.callback_query
    await q.answer()
    rows = await db.fetch("SELECT key, value FROM platform_settings WHERE key=ANY($1::text[])", GENERAL_KEYS)
    vals = {r["key"]: r["value"] for r in rows}
    txt = "🔧 <b>Platform Settings</b>\n"
    kb_rows = []
    for k in GENERAL_KEYS:
        cur = vals.get(k, "?")
        if k in BOOL_KEYS:
            on = _is_truthy(cur)
            label = f"{'🟢 ON' if on else '🔴 OFF'} — {k}"
            txt += f"\n• <b>{k}</b>: <code>{'ON' if on else 'OFF'}</code>"
            kb_rows.append([(label, f"admin:tog:{k}")])
        else:
            txt += f"\n• <b>{k}</b>: <code>{cur}</code>"
            kb_rows.append([(f"✏️ {k}", f"admin:set:{k}")])
    kb_rows.append([("💰 Adjust Pricing", "admin:settings:price")])
    kb_rows.append([("🔒 Force Sub", "admin:settings:forcesub")])
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def pricing_settings_panel(update, context):
    q = update.callback_query
    await q.answer()
    rows = await db.fetch("SELECT key, value FROM platform_settings WHERE key=ANY($1::text[])", PRICE_KEYS)
    vals = {r["key"]: r["value"] for r in rows}
    txt = "💰 <b>Pricing Adjustments</b>\n\nTap any value to change it.\n"
    kb_rows = []
    for k in PRICE_KEYS:
        cur = vals.get(k, "?")
        txt += f"\n• <b>{k}</b>: <code>{cur}</code>"
        kb_rows.append([(f"✏️ Adjust {k}", f"admin:set:{k}")])
    kb_rows.append([("🔄 Recalculate All Channels", "admin:pricing:recalc")])
    kb_rows.append(back("admin:settings"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def forcesub_panel(update, context):
    q = update.callback_query
    await q.answer()
    en = (await db.fetchval("SELECT value FROM platform_settings WHERE key='force_sub_enabled'") or "false")
    ch = (await db.fetchval("SELECT value FROM platform_settings WHERE key='force_sub_channel'") or "")
    on = _is_truthy(en)
    txt = (f"🔒 <b>Force Subscribe</b>\n\n"
           f"Status: <b>{'🟢 ON' if on else '🔴 OFF'}</b>\n"
           f"Channel: <code>{ch or '(not set)'}</code>\n\n"
           f"When ON, users who arrive via a referral link must join this channel before "
           f"the referral reward is credited to both parties.")
    rows = [
        [(f"{'🔴 Turn OFF' if on else '🟢 Turn ON'}", "admin:tog:force_sub_enabled")],
        [("✏️ Set Channel (@user or -100…id)", "admin:set:force_sub_channel")],
        back("admin:panel"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

@superadmin_only
async def toggle_setting(update, context):
    q = update.callback_query
    await q.answer()
    key = q.data.split(":", 2)[2]
    if key not in BOOL_KEYS:
        await q.answer("Not a toggle", show_alert=True); return
    cur = await db.fetchval("SELECT value FROM platform_settings WHERE key=$1", key)
    new_val = "false" if _is_truthy(cur) else "true"
    await db.execute("UPDATE platform_settings SET value=$2, updated_at=NOW(), updated_by=$3 WHERE key=$1", key, new_val, q.from_user.id)
    if key == "force_sub_enabled":
        await forcesub_panel(update, context)
    else:
        await settings_panel(update, context)

async def set_start(update, context):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    key = q.data.split(":",2)[2]
    if key not in KEYS:
        await q.answer("Bad key", show_alert=True); return ConversationHandler.END
    context.user_data["set_key"] = key
    cur = await db.fetchval("SELECT value FROM platform_settings WHERE key=$1", key)
    if key in PRICE_KEYS:
        back_to = "admin:settings:price"
    elif key in ("force_sub_enabled","force_sub_channel"):
        back_to = "admin:settings:forcesub"
    else:
        back_to = "admin:settings"
    await q.edit_message_text(f"Current <b>{key}</b>: <code>{cur}</code>\n\nSend new value:",
        parse_mode="HTML", reply_markup=kb([back(back_to)]))
    return EDIT

async def set_finish(update, context):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    key = context.user_data.pop("set_key", None)
    if not key: return ConversationHandler.END
    val = update.message.text.strip()
    await db.execute("UPDATE platform_settings SET value=$2, updated_at=NOW(), updated_by=$3 WHERE key=$1", key, val, update.effective_user.id)
    if key in PRICE_KEYS:
        back_to = "admin:settings:price"
    elif key in ("force_sub_enabled","force_sub_channel"):
        back_to = "admin:settings:forcesub"
    else:
        back_to = "admin:settings"
    await update.message.reply_text(f"✅ <b>{key}</b> = <code>{val}</code>", parse_mode="HTML",
        reply_markup=kb([back(back_to)]))
    return ConversationHandler.END

def build_settings_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(set_start, pattern=r"^admin:set:[a-z0-9_]+$")],
        states={EDIT:[MessageHandler(filters.TEXT & ~filters.COMMAND, set_finish)]},
        fallbacks=[_CmdHandler("cancel", _univ_cancel)],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

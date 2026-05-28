from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.decorators import superadmin_only
from utils.conv_fallbacks import nav_fallback
from utils.keyboards import kb, back
from database.pool import db

BOOL_KEYS = {"marketplace_enabled","maintenance_mode","watermark_enabled","force_sub_enabled","join_request_auto_accept"}

def _is_truthy(v):
    return str(v).strip().lower() in ("1","true","yes","on","t","y")

EDIT = 0

def _sanitize_surrogates(s):
    if not isinstance(s, str) or not s:
        return s or ""
    try:
        s.encode("utf-8")
        return s
    except UnicodeEncodeError:
        pass
    try:
        return s.encode("utf-16", "surrogatepass").decode("utf-16")
    except Exception:
        return s.encode("utf-8", "replace").decode("utf-8", "replace")

GENERAL_KEYS = [
    "platform_commission_percent","min_topup_credits","max_topup_credits","min_payout_credits",
    "credits_per_rupee","min_booking_hours","max_booking_hours","max_channels_per_owner",
    "max_active_bookings_per_advertiser","referral_bonus_credits","new_user_bonus_credits",
    "min_subscriber_count","inactive_days_remove",
    "marketplace_enabled","maintenance_mode","maintenance_message",
    "watermark_enabled","watermark_text",
]

FORCE_SUB_KEYS = ["force_sub_enabled","force_sub_channel"]

JOIN_REQ_KEYS = ["join_request_auto_accept","welcome_dm_message"]

PRICE_KEYS = [
    "base_price_per_post_credits","price_per_1k_subscribers","price_per_100_views",
    "activity_multiplier_high","activity_multiplier_medium","activity_multiplier_low",
    "min_listing_price","max_listing_price",
]

KEYS = GENERAL_KEYS + PRICE_KEYS + FORCE_SUB_KEYS + JOIN_REQ_KEYS


async def _upsert_setting(key, value, updated_by):
    await db.execute(
        """INSERT INTO platform_settings (key, value, updated_at, updated_by)
           VALUES ($1, $2, NOW(), $3)
           ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,
                                           updated_at=NOW(),
                                           updated_by=EXCLUDED.updated_by""",
        key, str(value), updated_by,
    )

@superadmin_only
async def settings_panel(update, context):
    q = update.callback_query
    await q.answer()
    rows = await db.fetch("SELECT key, value FROM platform_settings WHERE key=ANY($1::text[])", GENERAL_KEYS)
    vals = {r["key"]: r["value"] for r in rows}
    txt = "\U0001f527 <b>Platform Settings</b>\n"
    kb_rows = []
    for k in GENERAL_KEYS:
        cur = vals.get(k, "?")
        if k in BOOL_KEYS:
            on = _is_truthy(cur)
            label = f"{'\U0001f7e2 ON' if on else '\U0001f534 OFF'} \u2014 {k}"
            txt += f"\n\u2022 <b>{k}</b>: <code>{'ON' if on else 'OFF'}</code>"
            kb_rows.append([(label, f"admin:tog:{k}")])
        else:
            txt += f"\n\u2022 <b>{k}</b>: <code>{cur}</code>"
            kb_rows.append([(f"\u270f\ufe0f {k}", f"admin:set:{k}")])
    kb_rows.append([("\U0001f4b0 Adjust Pricing", "admin:settings:price")])
    kb_rows.append([("\U0001f512 Force Sub", "admin:settings:forcesub")])
    kb_rows.append(back("admin:panel"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def pricing_settings_panel(update, context):
    q = update.callback_query
    await q.answer()
    rows = await db.fetch("SELECT key, value FROM platform_settings WHERE key=ANY($1::text[])", PRICE_KEYS)
    vals = {r["key"]: r["value"] for r in rows}
    txt = "\U0001f4b0 <b>Pricing Adjustments</b>\n\nTap any value to change it.\n"
    kb_rows = []
    for k in PRICE_KEYS:
        cur = vals.get(k, "?")
        txt += f"\n\u2022 <b>{k}</b>: <code>{cur}</code>"
        kb_rows.append([(f"\u270f\ufe0f Adjust {k}", f"admin:set:{k}")])
    kb_rows.append([("\U0001f504 Recalculate All Channels", "admin:pricing:recalc")])
    kb_rows.append(back("admin:settings"))
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(kb_rows))

@superadmin_only
async def forcesub_panel(update, context):
    q = update.callback_query
    await q.answer()
    en = (await db.fetchval("SELECT value FROM platform_settings WHERE key='force_sub_enabled'") or "false")
    ch = (await db.fetchval("SELECT value FROM platform_settings WHERE key='force_sub_channel'") or "")
    on = _is_truthy(en)
    txt = (f"\U0001f512 <b>Force Subscribe</b>\n\n"
           f"Status: <b>{'\U0001f7e2 ON' if on else '\U0001f534 OFF'}</b>\n"
           f"Channel: <code>{ch or '(not set)'}</code>\n\n"
           f"When ON, users who arrive via a referral link must join this channel before "
           f"the referral reward is credited to both parties.")
    rows = [
        [(f"{'\U0001f534 Turn OFF' if on else '\U0001f7e2 Turn ON'}", "admin:tog:force_sub_enabled")],
        [("\u270f\ufe0f Set Channel (@user or -100\u2026id)", "admin:set:force_sub_channel")],
        back("admin:panel"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))


@superadmin_only
async def joinreq_panel(update, context):
    q = update.callback_query
    await q.answer()
    en = (await db.fetchval("SELECT value FROM platform_settings WHERE key='join_request_auto_accept'") or "false")
    msg = (await db.fetchval("SELECT value FROM platform_settings WHERE key='welcome_dm_message'") or "")
    msg = _sanitize_surrogates(msg)
    on = _is_truthy(en)
    preview = msg if len(msg) <= 300 else (msg[:300] + "\u2026")
    preview_html = preview.replace("<","&lt;").replace(">","&gt;")
    txt = (f"\U0001f4e8 <b>Join Requests</b>\n\n"
           f"Status: <b>{'\U0001f7e2 ON' if on else '\U0001f534 OFF'}</b>\n\n"
           f"When ON, the bot auto-accepts join requests in channels where it's an admin "
           f"with <i>Add Users / Invite Users</i> permission, then sends a welcome DM.\n\n"
           f"Placeholders: <code>{{user}}</code>, <code>{{channel}}</code>\n\n"
           f"<b>Current Welcome DM:</b>\n<blockquote>{preview_html or '(not set)'}</blockquote>")
    rows = [
        [(f"{'\U0001f534 Turn OFF' if on else '\U0001f7e2 Turn ON'}", "admin:tog:join_request_auto_accept")],
        [("\u270f\ufe0f Edit Welcome DM", "admin:set:welcome_dm_message")],
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
    await _upsert_setting(key, new_val, q.from_user.id)
    if key == "force_sub_enabled":
        await forcesub_panel(update, context)
    elif key == "join_request_auto_accept":
        await joinreq_panel(update, context)
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
    elif key in JOIN_REQ_KEYS:
        back_to = "admin:settings:joinreq"
    else:
        back_to = "admin:settings"
    await q.edit_message_text(f"Current <b>{key}</b>: <code>{cur}</code>\n\nSend new value:",
        parse_mode="HTML", reply_markup=kb([back(back_to)]))
    return EDIT

async def set_finish(update, context):
    if update.effective_user.id not in config.SUPERADMIN_IDS: return ConversationHandler.END
    key = context.user_data.pop("set_key", None)
    if not key: return ConversationHandler.END
    val = _sanitize_surrogates(update.message.text.strip())
    if key == "force_sub_channel":
        from handlers.start import normalize_force_sub_channel
        val = normalize_force_sub_channel(val)
    await _upsert_setting(key, val, update.effective_user.id)
    if key in PRICE_KEYS:
        back_to = "admin:settings:price"
    elif key in ("force_sub_enabled","force_sub_channel"):
        back_to = "admin:settings:forcesub"
    elif key in JOIN_REQ_KEYS:
        back_to = "admin:settings:joinreq"
    else:
        back_to = "admin:settings"
    await update.message.reply_text(f"\u2705 <b>{key}</b> = <code>{val}</code>", parse_mode="HTML",
        reply_markup=kb([back(back_to)]))
    return ConversationHandler.END

async def set_cancel(update, context):
    context.user_data.pop("set_key", None)
    data = update.callback_query.data if update.callback_query else ""
    try:
        if data == "admin:settings:price":
            await pricing_settings_panel(update, context)
        elif data == "admin:settings:forcesub":
            await forcesub_panel(update, context)
        elif data == "admin:settings:joinreq":
            await joinreq_panel(update, context)
        elif data == "admin:settings":
            await settings_panel(update, context)
        elif data == "admin:panel":
            from handlers.admin.dashboard import admin_panel
            await admin_panel(update, context)
        elif data == "home":
            from handlers.callbacks import home_handler
            await home_handler(update, context)
        else:
            await update.callback_query.answer()
    except Exception:
        try: await update.callback_query.answer()
        except Exception: pass
    return ConversationHandler.END

def build_settings_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(set_start, pattern=r"^admin:set:[a-z0-9_]+$")],
        states={EDIT:[
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_finish),
            CallbackQueryHandler(set_cancel, pattern=r"^(admin:settings(:price|:forcesub|:joinreq)?|admin:panel|home)$"),
        ]},
        fallbacks=[_CmdHandler("cancel", _univ_cancel), nav_fallback()],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

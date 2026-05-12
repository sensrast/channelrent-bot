from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.keyboards import kb, back
from utils.validators import normalize_channel_link, parse_int
from utils.formatters import activity_emoji
from services.channel_validator import verify_bot_is_admin
from services.pricing_engine import compute_activity, compute_price_per_hour, clamp_owner_price
from database.queries.channels import get_channel_by_chat, create_channel, list_all_categories, count_owner_channels, update_channel
from database.pool import db

log = logging.getLogger(__name__)

ASK_LINK, VERIFY, CATEGORY, ALLOWED, FORBIDDEN, APPROVAL, PRICE_MODE, CUSTOM_PRICE, CONFIRM = range(9)

async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    limit = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='max_channels_per_owner'") or 10)
    cur = await count_owner_channels(q.from_user.id)
    if cur >= limit:
        await q.edit_message_text(f"You already have {cur}/{limit} channels. Remove one first.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    context.user_data["setup"] = {}
    await q.edit_message_text(
        f"➕ <b>Add New Channel</b>\n\n"
        f"<b>Public channel:</b> send the @username or t.me link.\n"
        f"<b>Private channel:</b> forward ANY message from your channel here.\n\n"
        f"First add @{config.BOT_USERNAME} as admin with post + delete permissions.\n\n"
        f"/cancel to abort.", parse_mode="HTML")
    return ASK_LINK

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    target = None
    fwd_chat = getattr(msg, "forward_from_chat", None) or getattr(getattr(msg, "forward_origin", None), "chat", None)
    if fwd_chat and getattr(fwd_chat, "type", "") in ("channel","supergroup"):
        target = fwd_chat.id
        context.user_data["setup"]["handle"] = str(fwd_chat.id)
    elif msg.text:
        handle = normalize_channel_link(msg.text)
        context.user_data["setup"]["handle"] = ("@"+handle) if not handle.lstrip("-").isdigit() else handle
        target = context.user_data["setup"]["handle"]
    else:
        await msg.reply_text("Send the channel @username, t.me link, OR forward a message from the channel.")
        return ASK_LINK
    await msg.reply_text("⏳ Verifying bot admin status...")
    result = await verify_bot_is_admin(context.bot, target)
    if not result["ok"]:
        await msg.reply_text(f"❌ {result.get('reason','Not admin')}\n\nAdd @{config.BOT_USERNAME} as admin, then try again. Or /cancel.")
        return ASK_LINK
    chat_id = result["chat_id"]
    existing = await get_channel_by_chat(chat_id)
    if existing:
        same_owner = existing["owner_id"] == update.effective_user.id
        is_active = existing["is_active"] if not isinstance(existing, dict) else existing.get("is_active")
        if same_owner:
            if not is_active:
                await update_channel(existing["channel_id"],
                                     is_active=True, is_paused=False, is_listed=True,
                                     is_suspended=False)
                await msg.reply_text(
                    f"✅ Welcome back! <b>{existing['title']}</b> has been reactivated in your channels list.",
                    parse_mode="HTML")
                return ConversationHandler.END
            await msg.reply_text("ℹ️ This channel is already in your account.\n/cancel to exit.")
        else:
            if not is_active:
                await update_channel(existing["channel_id"],
                                     owner_id=update.effective_user.id,
                                     is_active=True, is_paused=False, is_listed=True,
                                     is_suspended=False)
                await msg.reply_text(
                    f"✅ <b>{existing['title']}</b> added to your channels.",
                    parse_mode="HTML")
                return ConversationHandler.END
            await msg.reply_text("⚠️ This channel is already listed by another user.")
        return ConversationHandler.END
    if (result.get("member_count") or 0) < 100:
        await msg.reply_text("❌ This channel has fewer than 100 subscribers. Minimum 100 required to list.")
        return ConversationHandler.END
    context.user_data["setup"].update({
        "chat_id": chat_id, "title": result["title"], "username": result.get("username"),
        "subscribers": result["member_count"], "avg_views": int(result["member_count"]*0.3),
    })
    return await _ask_category(msg, context)

async def _ask_category(target, context):
    cats = await list_all_categories()
    rows, cur = [], []
    for c in cats:
        cur.append((f"{c['emoji']} {c['name']}", f"owner:setup:cat:{c['category_id']}"))
        if len(cur)==2: rows.append(cur); cur=[]
    if cur: rows.append(cur)
    rows.append([("❌ Cancel","owner:setup:cancel")])
    if hasattr(target,"edit_message_text"):
        await target.edit_message_text("📂 Pick a category:", reply_markup=kb(rows))
    else:
        await target.reply_text("📂 Pick a category:", reply_markup=kb(rows))
    return CATEGORY

async def pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "owner:setup:cancel":
        context.user_data.pop("setup", None)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    cat_id = int(q.data.split(":")[3])
    context.user_data["setup"]["category_id"] = cat_id
    await q.edit_message_text("✅ Use default rules or write custom?", reply_markup=kb([
        [("📝 Default","owner:setup:rules:default")],
        [("✏️ Custom","owner:setup:rules:custom")],
    ]))
    return ALLOWED

async def rules_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":default"):
        context.user_data["setup"]["allowed"] = "Promotions, products, services, channels"
        context.user_data["setup"]["forbidden"] = "Adult content, scams, hate speech, MLM, gambling"
        return await _ask_approval(q, context)
    await q.edit_message_text("✏️ What content is ALLOWED on your channel?")
    return ALLOWED

async def allowed_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup"]["allowed"] = update.message.text[:500]
    await update.message.reply_text("What content is FORBIDDEN?")
    return FORBIDDEN

async def forbidden_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup"]["forbidden"] = update.message.text[:500]
    return await _ask_approval(update.message, context)

async def _ask_approval(target, context):
    rows = [[("✅ Auto-approve","owner:setup:apv:auto")],[("🔍 Manual review","owner:setup:apv:manual")]]
    if hasattr(target,"edit_message_text"):
        await target.edit_message_text("🔐 How handle bookings?", reply_markup=kb(rows))
    else:
        await target.reply_text("🔐 How handle bookings?", reply_markup=kb(rows))
    return APPROVAL

async def approval_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    s = context.user_data["setup"]
    s["auto_approve"] = q.data.endswith(":auto")
    score, tier, eng = compute_activity(s["subscribers"], s["avg_views"])
    price = compute_price_per_hour(s["subscribers"], s["avg_views"], tier)
    s["score"]=score; s["tier"]=tier; s["engagement"]=eng; s["suggested_price"]=price
    txt = (f"💰 <b>Suggested Pricing</b>\n\n"
           f"👥 Subscribers: {s['subscribers']:,}\n"
           f"👁️ Estimated views/24h: {s['avg_views']:,}\n"
           f"{activity_emoji(tier)} Activity: {tier.upper()} ({score}/100)\n\n"
           f"💰 Per Hour: <b>{price} cr</b>\n"
           f"📅 Per Day: {price*24} cr\n"
           f"📅 Per Week: {price*168} cr")
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb([
        [("✅ Use Suggested","owner:setup:price:auto")],
        [("✏️ Custom Price (±50%)","owner:setup:price:custom")],
    ]))
    return PRICE_MODE

async def price_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":auto"):
        context.user_data["setup"]["final_price"] = context.user_data["setup"]["suggested_price"]
        return await _show_confirm_setup(q, context)
    sp = context.user_data["setup"]["suggested_price"]
    lo, hi = max(config.MIN_LISTING_PRICE, int(sp*0.5)), min(config.MAX_LISTING_PRICE, int(sp*1.5))
    await q.edit_message_text(f"Enter custom price (cr/hr) between {lo} and {hi}:")
    return CUSTOM_PRICE

async def custom_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = parse_int(update.message.text)
    if not val:
        await update.message.reply_text("Invalid. Enter a number.")
        return CUSTOM_PRICE
    s = context.user_data["setup"]
    final = clamp_owner_price(s["suggested_price"], val)
    s["final_price"] = final
    s["owner_custom_price"] = val
    return await _show_confirm_setup(update.message, context)

async def _show_confirm_setup(target, context):
    s = context.user_data["setup"]
    txt = (f"📢 <b>Listing Summary</b>\n\n"
           f"Channel: <b>{s['title']}</b>\n"
           f"Subscribers: {s['subscribers']:,}\n"
           f"Activity: {s['tier'].upper()}\n"
           f"Price: <b>{s['final_price']} cr/hr</b>\n"
           f"Approval: {'Auto' if s['auto_approve'] else 'Manual'}\n\n"
           f"✅ {s['allowed']}\n❌ {s['forbidden']}")
    rows = [[("✅ List My Channel","owner:setup:confirm")],[("❌ Cancel","owner:setup:cancel")]]
    if hasattr(target,"edit_message_text"):
        await target.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    else:
        await target.reply_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return CONFIRM

async def confirm_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "owner:setup:cancel":
        context.user_data.pop("setup", None)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("home")]))
        return ConversationHandler.END
    s = context.user_data["setup"]
    from datetime import datetime, timezone
    cid = await create_channel(
        telegram_chat_id=s["chat_id"], owner_id=q.from_user.id,
        title=s["title"], username=s.get("username"),
        category_id=s["category_id"],
        subscriber_count=s["subscribers"], avg_views_24h=s["avg_views"],
        engagement_rate=s["engagement"], activity_score=s["score"], activity_tier=s["tier"],
        final_price_credits=s["final_price"], base_price_credits=s["suggested_price"],
        price_per_hour_credits=s["final_price"], owner_custom_price=s.get("owner_custom_price"),
        allowed_content=s["allowed"], forbidden_content=s["forbidden"],
        requires_approval=not s["auto_approve"], auto_approve=s["auto_approve"],
        is_listed=True, is_verified=True, listed_at=datetime.now(timezone.utc),
        stats_updated_at=datetime.now(timezone.utc),
    )
    await db.execute("UPDATE users SET is_owner=TRUE, total_channels_listed=total_channels_listed+1 WHERE user_id=$1", q.from_user.id)
    context.user_data.pop("setup", None)
    await q.edit_message_text(f"✅ Channel <b>{s['title']}</b> is now LIVE!\n💰 {s['final_price']} cr/hr",
        parse_mode="HTML", reply_markup=kb([[("📢 My Channels","owner:channels")],back("home")]))
    return ConversationHandler.END

def build_setup_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_channel_start, pattern=r"^owner:add$")],
        states={
            ASK_LINK: [MessageHandler((filters.TEXT | filters.FORWARDED) & ~filters.COMMAND, get_link)],
            CATEGORY: [CallbackQueryHandler(pick_category, pattern=r"^owner:setup:(cat:\d+|cancel)$")],
            ALLOWED: [
                CallbackQueryHandler(rules_choice, pattern=r"^owner:setup:rules:(default|custom)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, allowed_text),
            ],
            FORBIDDEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, forbidden_text)],
            APPROVAL: [CallbackQueryHandler(approval_choice, pattern=r"^owner:setup:apv:(auto|manual)$")],
            PRICE_MODE: [CallbackQueryHandler(price_mode, pattern=r"^owner:setup:price:(auto|custom)$")],
            CUSTOM_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_price)],
            CONFIRM: [CallbackQueryHandler(confirm_setup, pattern=r"^owner:setup:(confirm|cancel)$")],
        },
        fallbacks=[CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern=r"^home$")],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
import config
from utils.decorators import track_user, ban_check
from utils.keyboards import main_menu, kb
from utils.formatters import fmt_credits
from database.pool import db
from database.queries.users import get_user, set_referrer
from database.queries.credits import adjust_credits
from database.queries.channels import count_owner_channels
from services.notification_service import notify_superadmin

log = logging.getLogger(__name__)

_FORCE_SUB_ALERTED = set()

async def _maintenance(update, user_id):
    val = await db.fetchval("SELECT value FROM platform_settings WHERE key='maintenance_mode'")
    if (val or "false").lower() == "true" and user_id not in config.SUPERADMIN_IDS:
        msg = await db.fetchval("SELECT value FROM platform_settings WHERE key='maintenance_message'") or "Bot is under maintenance."
        if update.message:
            await update.message.reply_text(f"🛠️ {msg}")
        return True
    return False

async def _force_sub_check(bot, user_id):
    en = (await db.fetchval("SELECT value FROM platform_settings WHERE key='force_sub_enabled'") or "false").lower() == "true"
    ch = (await db.fetchval("SELECT value FROM platform_settings WHERE key='force_sub_channel'") or "").strip()
    if not en or not ch:
        return False, ch, True, True
    target = ch
    if target.lstrip("-").isdigit():
        target = int(target)
    try:
        m = await bot.get_chat_member(target, user_id)
        ok = m.status in ("member","administrator","creator","restricted")
        return True, ch, ok, True
    except BadRequest as e:
        s = str(e).lower()
        if "user not found" in s:
            return True, ch, False, True
        await _alert_force_sub_misconfig(bot, ch, str(e))
        return True, ch, False, False
    except Forbidden as e:
        await _alert_force_sub_misconfig(bot, ch, str(e))
        return True, ch, False, False
    except TelegramError as e:
        log.warning("force sub check failed: %s", e)
        await _alert_force_sub_misconfig(bot, ch, str(e))
        return True, ch, False, False

async def _alert_force_sub_misconfig(bot, channel, err):
    key = (channel or "").strip().lower()
    if key in _FORCE_SUB_ALERTED:
        return
    _FORCE_SUB_ALERTED.add(key)
    try:
        await notify_superadmin(
            bot,
            (
                "⚠️ <b>Force-Sub misconfigured</b>\n"
                f"Channel: <code>{channel}</code>\n"
                f"Error: <code>{err[:200]}</code>\n\n"
                f"Please add <b>@{config.BOT_USERNAME}</b> as an admin of the "
                f"force-sub channel with permission to view members."
            ),
        )
    except Exception as e:
        log.warning("force-sub alert failed: %s", e)

def _force_sub_keyboard(channel):
    handle = channel.lstrip("@")
    if handle.lstrip("-").isdigit():
        url = None
    else:
        url = f"https://t.me/{handle}"
    rows = []
    if url:
        rows.append([InlineKeyboardButton("📢 Join Channel", url=url)])
    rows.append([InlineKeyboardButton("✅ I Joined — Verify", callback_data="common:fsub:verify")])
    return InlineKeyboardMarkup(rows)

@track_user
@ban_check
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if await _maintenance(update, u.id): return
    user = await get_user(u.id)
    is_new = user["credits_total_purchased"] == 0 and user["credits_balance"] == 0 and user["registered_at"] == user["last_active"]
    args = context.args or []
    if args:
        arg = args[0]
        if arg.startswith("ref_"):
            try:
                ref_id = int(arg[4:])
                if ref_id != u.id and user["referred_by"] is None and not user["referral_credited"]:
                    referrer = await get_user(ref_id)
                    if referrer and not referrer["is_banned"]:
                        await db.execute("UPDATE users SET pending_referrer_id=$2 WHERE user_id=$1", u.id, ref_id)
                        fs_en, fs_ch, is_mem, bot_ok = await _force_sub_check(context.bot, u.id)
                        if fs_en and fs_ch and (not is_mem or not bot_ok):
                            await update.message.reply_text(
                                "🔗 You were invited by a friend!\n\nJoin our channel first to unlock your reward:",
                                reply_markup=_force_sub_keyboard(fs_ch))
                            return
                        await _credit_referral(context.bot, u.id, ref_id, u.first_name)
            except Exception as e:
                log.debug("ref parse failed: %s", e)
    if is_new:
        bonus = int(float(await db.fetchval("SELECT value FROM platform_settings WHERE key='new_user_bonus_credits'") or 25))
        if bonus > 0:
            async with db.acquire() as conn:
                async with conn.transaction():
                    await adjust_credits(conn, u.id, bonus, "platform_bonus", description="Welcome bonus")
            await update.message.reply_text(f"🎁 Welcome bonus: <b>{bonus} credits</b> added!", parse_mode="HTML")
    user = await get_user(u.id)
    n_channels = await count_owner_channels(u.id)
    is_admin = u.id in config.SUPERADMIN_IDS
    text = (f"🏪 <b>{config.PLATFORM_NAME}</b> — Channel Ad Marketplace\n\n"
            f"👋 Hey {u.first_name or 'there'}!\n"
            f"💰 Credits: <b>{fmt_credits(user['credits_balance'])}</b>"
            + (f" | 📈 Earnings: <b>{fmt_credits(user['earnings_pending'])}</b>" if n_channels else "")
            + "\n\nChoose an option below:")
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu(n_channels>0, is_admin))

async def _credit_referral(bot, new_user_id, ref_id, first_name):
    row = await db.fetchrow("SELECT referral_credited FROM users WHERE user_id=$1", new_user_id)
    if row and row["referral_credited"]:
        return
    bonus = int(float(await db.fetchval("SELECT value FROM platform_settings WHERE key='referral_bonus_credits'") or 50))
    await set_referrer(new_user_id, ref_id)
    async with db.acquire() as conn:
        async with conn.transaction():
            await adjust_credits(conn, ref_id, bonus, "referral_bonus", description=f"Referred {first_name}")
            await adjust_credits(conn, new_user_id, bonus, "referral_bonus", description="Joined via referral")
            await conn.execute("UPDATE users SET referral_credited=TRUE, pending_referrer_id=NULL WHERE user_id=$1", new_user_id)
    try:
        await bot.send_message(ref_id, f"🎉 Your friend {first_name} joined! +{bonus} credits added.")
    except Exception: pass
    try:
        await bot.send_message(new_user_id, f"🎉 Referral reward unlocked! +{bonus} credits.")
    except Exception: pass

async def force_sub_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    row = await get_user(u.id)
    if not row or not row["pending_referrer_id"] or row["referral_credited"]:
        try: await q.edit_message_text("✅ Nothing to verify. Tap /start.")
        except Exception: pass
        return
    fs_en, fs_ch, is_mem, bot_ok = await _force_sub_check(context.bot, u.id)
    if fs_en and not is_mem:
        try:
            await q.answer("Not joined yet. Please join the channel first.", show_alert=True)
        except Exception: pass
        return
    await _credit_referral(context.bot, u.id, row["pending_referrer_id"], u.first_name)
    try:
        await q.edit_message_text("🎉 Verified! Referral reward credited. Tap /start to begin.")
    except Exception: pass

async def universal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Cancelled. Tap /start to return to main menu.")
    return -1

async def channel_post_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cp = update.channel_post or update.edited_channel_post
    if not cp: return
    try:
        await db.execute("UPDATE channels SET last_post_at=NOW() WHERE telegram_chat_id=$1", cp.chat.id)
    except Exception: pass

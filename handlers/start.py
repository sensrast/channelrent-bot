import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
from utils.decorators import track_user, ban_check
from utils.keyboards import main_menu
from utils.formatters import fmt_credits
from database.pool import db
from database.queries.users import get_user, set_referrer
from database.queries.credits import adjust_credits
from database.queries.channels import count_owner_channels

log = logging.getLogger(__name__)

async def _maintenance(update, user_id):
    val = await db.fetchval("SELECT value FROM platform_settings WHERE key='maintenance_mode'")
    if (val or "false").lower() == "true" and user_id not in config.SUPERADMIN_IDS:
        msg = await db.fetchval("SELECT value FROM platform_settings WHERE key='maintenance_message'") or "Bot is under maintenance."
        if update.message:
            await update.message.reply_text(f"🛠️ {msg}")
        return True
    return False

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
                if ref_id != u.id and user["referred_by"] is None:
                    referrer = await get_user(ref_id)
                    if referrer and not referrer["is_banned"]:
                        await set_referrer(u.id, ref_id)
                        bonus = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='referral_bonus_credits'") or 50)
                        async with db.acquire() as conn:
                            async with conn.transaction():
                                await adjust_credits(conn, ref_id, bonus, "referral_bonus", description=f"Referred {u.first_name}")
                        try:
                            await context.bot.send_message(ref_id, f"🎉 Your friend {u.first_name} joined! +{bonus} credits added.")
                        except Exception: pass
            except Exception as e:
                log.debug("ref parse failed: %s", e)
    if is_new:
        bonus = int(await db.fetchval("SELECT value FROM platform_settings WHERE key='new_user_bonus_credits'") or 25)
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

async def universal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Cancelled. Tap /start to return to main menu.")
    return -1  # ConversationHandler.END

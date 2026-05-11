import logging
from telegram import Bot
from telegram.error import Forbidden, TelegramError
from database.pool import db
from database.queries.users import mark_blocked_bot
import config

log = logging.getLogger(__name__)

async def _send(bot, user_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        return True
    except Forbidden:
        await mark_blocked_bot(user_id)
        return False
    except TelegramError as e:
        log.warning("notify failed user=%s err=%s", user_id, e)
        return False

async def log_notif(user_id, ntype, booking_id=None, preview=None, delivered=True):
    try:
        await db.execute("INSERT INTO notifications (user_id,type,booking_id,message_preview,delivered) VALUES ($1,$2,$3,$4,$5)",
                         user_id, ntype, booking_id, (preview or "")[:200], delivered)
    except Exception as e:
        log.debug("log_notif failed: %s", e)

async def notify(bot, user_id, ntype, text, booking_id=None, reply_markup=None):
    ok = await _send(bot, user_id, text, reply_markup=reply_markup)
    await log_notif(user_id, ntype, booking_id, text, ok)
    return ok

async def notify_superadmin(bot, text, reply_markup=None):
    for sid in config.SUPERADMIN_IDS:
        await _send(bot, sid, text, reply_markup=reply_markup)

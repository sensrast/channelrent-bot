import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
from database.pool import db

log = logging.getLogger(__name__)

DEFAULT_WELCOME = "👋 Welcome! Thanks for joining. We're glad to have you here."

def _is_truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on", "t", "y")

async def _enabled() -> bool:
    try:
        v = await db.fetchval("SELECT value FROM platform_settings WHERE key='join_request_auto_accept'")
        return _is_truthy(v)
    except Exception as e:
        log.warning("join_request enabled check failed: %s", e)
        return False

async def _welcome_text() -> str:
    try:
        v = await db.fetchval("SELECT value FROM platform_settings WHERE key='welcome_dm_message'")
        return (v or DEFAULT_WELCOME).strip() or DEFAULT_WELCOME
    except Exception:
        return DEFAULT_WELCOME

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    if not req:
        return
    if not await _enabled():
        return
    chat = req.chat
    user = req.from_user
    try:
        await context.bot.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
        log.info("Approved join request: chat=%s user=%s", chat.id, user.id)
    except (Forbidden, BadRequest, TelegramError) as e:
        log.warning("approve_chat_join_request failed chat=%s user=%s: %s", chat.id, user.id, e)
        return
    text = await _welcome_text()
    chat_title = chat.title or "the channel"
    text = text.replace("{user}", user.first_name or "there").replace("{channel}", chat_title)
    try:
        await context.bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")
    except Forbidden:
        log.info("Welcome DM blocked by user %s", user.id)
    except (BadRequest, TelegramError) as e:
        log.warning("Welcome DM send failed user=%s: %s", user.id, e)

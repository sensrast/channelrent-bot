import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
from database.pool import db

log = logging.getLogger(__name__)

DEFAULT_WELCOME = "👋 Welcome! Thanks for joining. We're glad to have you here."

def _is_truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on", "t", "y")

async def _global_enabled():
    try:
        v = await db.fetchval("SELECT value FROM platform_settings WHERE key='join_request_auto_accept'")
        return _is_truthy(v)
    except Exception as e:
        log.warning("join_request global enabled check failed: %s", e)
        return False

async def _channel_enabled(chat_id):
    try:
        v = await db.fetchval("SELECT auto_accept_requests FROM channels WHERE telegram_chat_id=$1", chat_id)
        return bool(v)
    except Exception as e:
        log.warning("join_request channel enabled check failed chat=%s: %s", chat_id, e)
        return False

async def _welcome_text():
    try:
        v = await db.fetchval("SELECT value FROM platform_settings WHERE key='welcome_dm_message'")
        return (v or DEFAULT_WELCOME).strip() or DEFAULT_WELCOME
    except Exception:
        return DEFAULT_WELCOME

async def handle_join_request(update, context):
    req = update.chat_join_request
    if not req:
        return
    chat = req.chat
    user = req.from_user
    if not (await _global_enabled() or await _channel_enabled(chat.id)):
        return
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

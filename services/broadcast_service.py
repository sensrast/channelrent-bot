import json
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, BadRequest, TelegramError
import config

log = logging.getLogger(__name__)

DEFAULT_WATERMARK = f"\n\n📢 Promoted via {config.PLATFORM_NAME}"

async def _watermark():
    try:
        from database.pool import db
        en = (await db.fetchval("SELECT value FROM platform_settings WHERE key='watermark_enabled'") or "true").lower() == "true"
        if not en:
            return ""
        txt = await db.fetchval("SELECT value FROM platform_settings WHERE key='watermark_text'")
        if txt:
            return "\n\n" + txt
        return DEFAULT_WATERMARK
    except Exception:
        return DEFAULT_WATERMARK

def _buttons(buttons_json):
    if not buttons_json: return None
    try:
        data = buttons_json if isinstance(buttons_json, list) else json.loads(buttons_json)
        rows = [[InlineKeyboardButton(label, url=url) for label, url in data]]
        return InlineKeyboardMarkup(rows)
    except Exception:
        return None

async def _safe_pin(bot: Bot, chat_id, message_id):
    try:
        await bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=True)
    except Exception as e:
        log.debug("pin skipped for %s/%s: %s", chat_id, message_id, e)
        return
    for delta in (1, 2):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id + delta)
        except Exception:
            pass

async def post_to_channel(bot: Bot, booking, watermark=True):
    chat_id = booking["telegram_chat_id"]
    ct = booking["content_type"]
    wm = await _watermark() if watermark else ""
    caption = (booking.get("caption") or "") + wm
    text = (booking.get("content_text") or "") + wm
    markup = _buttons(booking.get("inline_buttons_json"))
    if ct == "text":
        msg = await bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=False)
    elif ct == "photo":
        msg = await bot.send_photo(chat_id, booking["media_file_id"], caption=caption, reply_markup=markup)
    elif ct == "document":
        msg = await bot.send_document(chat_id, booking["media_file_id"], caption=caption, reply_markup=markup)
    else:
        raise ValueError(f"Unsupported content_type {ct}")
    await _safe_pin(bot, chat_id, msg.message_id)
    return msg.message_id

async def delete_from_channel(bot: Bot, chat_id, message_id):
    try:
        await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except BadRequest as e:
        log.info("delete failed bad request: %s", e); return False
    except Forbidden as e:
        log.info("delete forbidden: %s", e); return False
    except TelegramError as e:
        log.warning("delete error: %s", e); return False

DELETED_HINTS = (
    "message to edit not found",
    "message to delete not found",
    "message to forward not found",
    "message to copy not found",
    "message to unpin not found",
    "message_id_invalid",
    "message id invalid",
    "message not found",
    "message identifier is not specified",
)

def _is_deleted_error(text):
    s = (text or "").lower()
    for h in DELETED_HINTS:
        if h in s:
            return True
    return False

async def message_exists(bot: Bot, from_chat_id, message_id, probe_chat_id=None, inline_buttons_json=None):
    """Reliably determine whether the channel post is still alive.

    Probe order (strongest first):
      1) copyMessage to superadmin DM - immediate "copy not found" when deleted.
      2) forwardMessage to superadmin DM - similar strong signal.
      3) editMessageReplyMarkup (same markup) - non-destructive ping.
      4) unpin+ re-pin - last resort.

    Returns True (alive) on inconclusive errors so we never refund a user
    from a transient Telegram error. Deletion is only reported when a
    probe returns a strong 'not found' signal.
    """
    # NOTE: copy/forward probes to admin DM were removed - they spammed the admin
    # with every active promotion message every few seconds. We now rely solely on
    # non-destructive edit_message_reply_markup probing below.
    _ = probe_chat_id  # kept for backward-compatible signature
    markup = _buttons(inline_buttons_json)
    try:
        await bot.edit_message_reply_markup(chat_id=from_chat_id, message_id=message_id, reply_markup=markup)
        return True
    except BadRequest as e:
        es = str(e).lower()
        if "not modified" in es or "exactly the same" in es:
            return True
        if _is_deleted_error(es):
            return False
        log.debug("edit-probe inconclusive: %s", e)
    except Forbidden:
        pass
    except TelegramError as e:
        log.debug("edit-probe telegram err: %s", e)

    try:
        await bot.unpin_chat_message(chat_id=from_chat_id, message_id=message_id)
        try:
            await bot.pin_chat_message(chat_id=from_chat_id, message_id=message_id, disable_notification=True)
        except Exception:
            pass
        return True
    except BadRequest as e:
        es = str(e).lower()
        if "not pinned" in es or "is not pinned" in es or "not modified" in es:
            return True
        if _is_deleted_error(es):
            return False
    except Forbidden:
        pass
    except TelegramError:
        pass
    return True

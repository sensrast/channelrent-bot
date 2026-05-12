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
    return msg.message_id

async def delete_from_channel(bot: Bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except BadRequest as e:
        log.info("delete failed bad request: %s", e); return False
    except Forbidden as e:
        log.info("delete forbidden: %s", e); return False
    except TelegramError as e:
        log.warning("delete error: %s", e); return False

DELETED_HINTS = ("not found", "message to forward", "message_id_invalid",
                 "message to copy", "message identifier is not specified",
                 "message to be forwarded", "message can't be forwarded",
                 "message_to_forward_not_found", "message to delete not found",
                 "message id invalid")

async def message_exists(bot: Bot, from_chat_id, message_id, target_chat_id):
    """Probe whether the original channel message still exists.

    Primary: forward_message to admin probe chat (silently) then delete the copy.
    Telegram returns "message to forward not found" / MESSAGE_ID_INVALID when the
    original message was deleted by the channel owner. This is non-destructive
    to the live ad (no buttons removed, no edits to user-visible content).

    Fallback: copy_message + delete.
    """
    if target_chat_id:
        try:
            fwd = await bot.forward_message(chat_id=target_chat_id, from_chat_id=from_chat_id,
                                            message_id=message_id, disable_notification=True)
            try:
                await bot.delete_message(target_chat_id, fwd.message_id)
            except Exception:
                pass
            return True
        except BadRequest as e:
            s = str(e).lower()
            for h in DELETED_HINTS:
                if h in s:
                    return False
            if "message to forward" in s or "message_id_invalid" in s or "message not found" in s or "message to copy" in s:
                return False
        except Forbidden:
            pass
        except TelegramError as e:
            log.debug("forward probe err: %s", e)
        try:
            cp = await bot.copy_message(chat_id=target_chat_id, from_chat_id=from_chat_id,
                                        message_id=message_id, disable_notification=True)
            try:
                await bot.delete_message(target_chat_id, cp.message_id)
            except Exception:
                pass
            return True
        except BadRequest as e:
            s = str(e).lower()
            for h in DELETED_HINTS:
                if h in s:
                    return False
            if "message to copy" in s or "message_id_invalid" in s or "message not found" in s:
                return False
        except Forbidden:
            return True
        except TelegramError:
            return True
    try:
        await bot.unpin_chat_message(chat_id=from_chat_id, message_id=message_id)
        return True
    except BadRequest as e:
        s = str(e).lower()
        if "not pinned" in s or "is not pinned" in s or "not modified" in s:
            return True
        for h in DELETED_HINTS:
            if h in s:
                return False
        if "message to unpin" in s or "message_id_invalid" in s or "message not found" in s:
            return False
    except Forbidden:
        pass
    except TelegramError as e:
        log.debug("unpin probe err: %s", e)
    return True

import logging
log = logging.getLogger(__name__)


def _get(row, key, default=None):
    if row is None:
        return default
    try:
        return row[key] if key in row else default
    except (KeyError, TypeError):
        pass
    try:
        return getattr(row, key, default)
    except Exception:
        return default


async def get_channel_link(row, bot=None):
    """Return a reachable link for a channel row.

    Accepts asyncpg Record, dict, or object. Resolves public username, stored
    invite link, or exports a fresh invite link for private channels.
    """
    if not row:
        return None
    username = _get(row, "channel_username") or _get(row, "username")
    if username:
        return f"https://t.me/{str(username).lstrip('@')}"
    invite = _get(row, "invite_link")
    if invite:
        return invite
    chat_id = _get(row, "telegram_chat_id") or _get(row, "chat_id")
    if chat_id and bot:
        try:
            chat = await bot.get_chat(chat_id)
            if getattr(chat, "username", None):
                return f"https://t.me/{chat.username}"
            inv = getattr(chat, "invite_link", None)
            if inv:
                return inv
            try:
                inv = await bot.export_chat_invite_link(chat_id)
                if inv:
                    return inv
            except Exception as e:
                log.debug("export_chat_invite_link failed for %s: %s", chat_id, e)
        except Exception as e:
            log.debug("get_chat failed for %s: %s", chat_id, e)
    if chat_id:
        try:
            cid = int(chat_id)
            if cid < 0:
                short = str(cid).replace("-100", "").lstrip("-")
                return f"https://t.me/c/{short}"
        except Exception:
            pass
    return None


# Backward-compatible alias (older code used get_channel_display_link).
get_channel_display_link = get_channel_link

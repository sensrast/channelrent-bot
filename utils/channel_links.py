import logging
log = logging.getLogger(__name__)

# In-memory cache so we don't recreate join-request invite links every render.
_join_request_cache = {}


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


async def get_channel_link(row, bot=None, require_approval=False):
    """Return a reachable link for a channel row.

    Accepts asyncpg Record, dict, or object. Resolves public username, stored
    invite link, or exports a fresh invite link for private channels.

    When require_approval=True and the channel is private (no public username),
    a join-request invite link is created/cached so joins require admin approval.
    """
    if not row:
        return None
    username = _get(row, "channel_username") or _get(row, "username")
    if username:
        return f"https://t.me/{str(username).lstrip('@')}"
    chat_id = _get(row, "telegram_chat_id") or _get(row, "chat_id")

    if require_approval and chat_id and bot:
        cached = _join_request_cache.get(chat_id)
        if cached:
            return cached
        try:
            invite = await bot.create_chat_invite_link(
                chat_id, creates_join_request=True, name="ChannelRent Approval"
            )
            link = getattr(invite, "invite_link", None)
            if link:
                _join_request_cache[chat_id] = link
                return link
        except Exception as e:
            log.debug("create_chat_invite_link (join_request) failed for %s: %s", chat_id, e)

    invite = _get(row, "invite_link")
    if invite:
        return invite
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

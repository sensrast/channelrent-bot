import logging
log = logging.getLogger(__name__)

async def get_channel_display_link(bot, row):
    """Return a reachable link for a channel row.

    The row can come from either channels or a JOIN result. Acceptable fields:
    - channel_username (from channels)
    - telegram_chat_id
    - invite_link
    """
    if not row:
        return None
    username = row.get("channel_username") if isinstance(row, dict) else getattr(row, "channel_username", None)
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    invite = row.get("invite_link") if isinstance(row, dict) else getattr(row, "invite_link", None)
    chat_id = row.get("telegram_chat_id") if isinstance(row, dict) else getattr(row, "telegram_chat_id", None)
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
                log.debug("export_chat_invite_link failed: %s", e)
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

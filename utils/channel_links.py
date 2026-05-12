import logging
log = logging.getLogger(__name__)

async def get_channel_link(channel, bot=None):
    """Return a URL to visit this channel. Public username first, then stored
    invite_link, then bot.get_chat().invite_link, then export/create via bot
    (and persists the result)."""
    if channel is None:
        return None
    def _val(key):
        if isinstance(channel, dict):
            return channel.get(key)
        try:
            return channel[key]
        except Exception:
            return None
    u = _val("username")
    if u:
        return f"https://t.me/{str(u).lstrip('@')}"
    inv = _val("invite_link")
    if inv:
        return inv
    if bot is None:
        return None
    chat_id = _val("telegram_chat_id")
    channel_id = _val("channel_id")
    if not chat_id:
        return None
    try:
        chat = await bot.get_chat(chat_id)
        link = getattr(chat, "invite_link", None)
        if link:
            try:
                from database.queries.channels import update_channel
                if channel_id:
                    await update_channel(channel_id, invite_link=link)
            except Exception as e:
                log.warning("persist get_chat invite link failed: %s", e)
            return link
    except Exception as e:
        log.debug("get_chat invite failed for %s: %s", chat_id, e)
    try:
        url = await bot.export_chat_invite_link(chat_id=chat_id)
        if url:
            try:
                from database.queries.channels import update_channel
                if channel_id:
                    await update_channel(channel_id, invite_link=url)
            except Exception as e:
                log.warning("persist export invite link failed: %s", e)
            return url
    except Exception as e:
        log.debug("export invite link failed for %s: %s", chat_id, e)
    try:
        link_obj = await bot.create_chat_invite_link(chat_id=chat_id, creates_join_request=False)
        url = link_obj.invite_link
        try:
            from database.queries.channels import update_channel
            if channel_id:
                await update_channel(channel_id, invite_link=url)
        except Exception as e:
            log.warning("persist create invite link failed: %s", e)
        return url
    except Exception as e:
        log.info("create invite link failed for %s: %s", chat_id, e)
        return None

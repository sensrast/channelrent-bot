import logging
log = logging.getLogger(__name__)

async def get_channel_link(channel, bot=None):
    """Return a URL to visit this channel. Uses public username, then stored invite_link,
    then tries to create one via bot (and persists it)."""
    if channel is None:
        return None
    u = channel.get("username") if isinstance(channel, dict) else channel["username"] if "username" in channel.keys() else None
    if u:
        return f"https://t.me/{u}"
    inv = None
    try:
        inv = channel["invite_link"]
    except Exception:
        inv = channel.get("invite_link") if isinstance(channel, dict) else None
    if inv:
        return inv
    if bot is None:
        return None
    try:
        chat_id = channel["telegram_chat_id"] if "telegram_chat_id" in channel.keys() else channel.get("telegram_chat_id")
        link_obj = await bot.create_chat_invite_link(chat_id=chat_id, creates_join_request=False)
        url = link_obj.invite_link
        try:
            from database.queries.channels import update_channel
            await update_channel(channel["channel_id"], invite_link=url)
        except Exception as e:
            log.warning("persist invite link failed: %s", e)
        return url
    except Exception as e:
        log.info("create invite link failed: %s", e)
        return None

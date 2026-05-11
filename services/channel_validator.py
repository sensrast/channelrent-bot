import logging
from telegram import Bot
from telegram.error import TelegramError

log = logging.getLogger(__name__)

async def verify_bot_is_admin(bot: Bot, chat_id_or_username: str):
    try:
        chat = await bot.get_chat(chat_id_or_username)
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
        is_admin = member.status in ("administrator","creator")
        can_post = getattr(member, "can_post_messages", True) is not False
        can_delete = getattr(member, "can_delete_messages", True) is not False
        return {
            "ok": is_admin and can_post and can_delete,
            "chat_id": chat.id,
            "title": chat.title or "",
            "username": chat.username,
            "type": chat.type,
            "member_count": (await bot.get_chat_member_count(chat.id)) if is_admin else 0,
            "reason": None if (is_admin and can_post and can_delete) else "Bot needs admin with post + delete permissions",
        }
    except TelegramError as e:
        log.warning("verify channel error: %s", e)
        return {"ok": False, "reason": str(e)}

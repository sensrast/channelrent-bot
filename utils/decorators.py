import functools
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
from database.queries.users import get_user, upsert_user

log = logging.getLogger(__name__)

def superadmin_only(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        u = update.effective_user
        if not u or u.id not in config.SUPERADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("⛔ Admins only", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ Admins only.")
            return
        return await func(update, context, *a, **kw)
    return wrapper

def track_user(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        u = update.effective_user
        if u:
            try:
                await upsert_user(u.id, u.username, u.first_name, u.last_name, u.language_code or "en")
            except Exception as e:
                log.warning("track_user upsert failed: %s", e)
        return await func(update, context, *a, **kw)
    return wrapper

def ban_check(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        u = update.effective_user
        if u:
            row = await get_user(u.id)
            if row and row["is_banned"]:
                msg = f"🚫 Your account has been suspended.\nReason: {row['ban_reason'] or 'Not specified'}\nContact: @{config.SUPPORT_USERNAME}"
                if update.callback_query:
                    await update.callback_query.answer(msg, show_alert=True)
                elif update.message:
                    await update.message.reply_text(msg)
                return
        return await func(update, context, *a, **kw)
    return wrapper

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
import config
from utils.decorators import track_user, ban_check
from utils.keyboards import main_menu, kb
from utils.formatters import fmt_credits
from database.pool import db
from database.queries.users import get_user, set_referrer
from database.queries.credits import adjust_credits
from database.queries.channels import count_owner_channels
from services.notification_service import notify_superadmin

log = logging.getLogger(__name__)

_FORCE_SUB_ALERTED = set()

async def _maintenance(update, user_id):
    val = await db.fetchval("SELECT value FROM platform_settings WHERE key='maintenance_mode'")
    if (val or "false").lower() == "true" and user_id not in config.SUPERADMIN_IDS:
        msg = await db.fetchval("SELECT value FROM platform_settings WHERE key='maintenance_message'") or "Bot is under maintenance."
        if update.message:
            await update.message.reply_text(f"🛠️ {msg}")
        return True
    return False

def normalize_force_sub_channel(raw):
    """Normalize a stored force-sub channel value to either '@username' or a
    numeric chat id string ('-100...'). Accepts t.me links, https URLs, plain
    handles, raw -100 ids, or already-prefixed @handles. Returns '' if blank."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = s.replace("https://", "").replace("http://", "")
    for prefix in ("telegram.me/", "t.me/", "telegram.dog/"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.split("?", 1)[0].split("/", 1)[0].strip()
    s = s.lstrip("@").strip()
    if not s:
        return ""
    if s.lstrip("-").isdigit():
        return s
    return "@" + s

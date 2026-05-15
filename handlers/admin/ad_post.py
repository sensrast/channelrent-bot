import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from utils.validators import parse_buttons
from database.queries.channels import list_owner_channels, list_all_verified

log = logging.getLogger(__name__)

(AP_PICK_LIST, AP_PICK_CHANNELS, AP_GET_CONTENT, AP_ASK_BUTTONS,
 AP_GET_BUTTONS, AP_ASK_PIN, AP_ASK_DELETE, AP_CONFIRM) = range(8)

PAGE_SIZE = 10

DELETE_PRESETS = [
    ("1 hour", 60),
    ("6 hours", 6 * 60),
    ("12 hours", 12 * 60),
    ("24 hours", 24 * 60),
    ("3 days", 3 * 24 * 60),
    ("7 days", 7 * 24 * 60),
]


def _state(context):
    if "admin_post" not in context.user_data:
        context.user_data["admin_post"] = {
            "list_type": None,
            "channels": [],
            "selected": set(),
            "page": 0,
            "content_type": None,
            "content_text": None,
            "media_file_id": None,
            "caption": None,
            "buttons": None,
            "pin": False,
            "auto_delete_minutes": None,
        }
    return context.user_data["admin_post"]
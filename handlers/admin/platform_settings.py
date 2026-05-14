from telegram.ext import CommandHandler as _CmdHandler
async def _univ_cancel(u,c):
    from telegram.ext import ConversationHandler
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from database.pool import db

BOOL_KEYS = {"marketplace_enabled","maintenance_mode","watermark_enabled","force_sub_enabled","join_request_auto_accept"}

def _is_truthy(v):
    return str(v).strip().lower() in ("1","true","yes","on","t","y")

EDIT = 0

GENERAL_KEYS = [
    "platform_commission_percent","min_topup_credits","max_topup_credits","min_payout_credits",
    "credits_per_rupee","min_booking_hours","max_booking_hours","max_channels_per_owner",
    "max_active_bookings_per_advertiser","referral_bonus_credits","new_user_bonus_credits",
    "min_subscriber_count","inactive_days_remove",
    "marketplace_enabled","maintenance_mode","maintenance_message",
    "watermark_enabled","watermark_text",
]

FORCE_SUB_KEYS = ["force_sub_enabled","force_sub_channel"]

JOIN_REQ_KEYS = ["join_request_auto_accept","welcome_dm_message"]

PRICE_KEYS = [
    "base_price_per_post_credits","price_per_1k_subscribers","price_per_100_views",
    "activity_multiplier_high","activity_multiplier_medium","activity_multiplier_low",
    "min_listing_price","max_listing_price",
]

KEYS = GENERAL_KEYS + PRICE_KEYS + FORCE_SUB_KEYS + JOIN_REQ_KEYS

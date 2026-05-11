import os
from dotenv import load_dotenv

load_dotenv()

def _int(k, d): 
    try: return int(os.getenv(k, d))
    except: return int(d)
def _float(k, d):
    try: return float(os.getenv(k, d))
    except: return float(d)
def _bool(k, d="false"):
    return str(os.getenv(k, d)).lower() in ("1","true","yes","on")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Tele_marketplace_bot").lstrip("@")
PLATFORM_NAME = os.getenv("PLATFORM_NAME", "ChannelRent")
SUPERADMIN_IDS = [int(x) for x in os.getenv("SUPERADMIN_IDS", "").split(",") if x.strip().isdigit()]

DATABASE_URL = os.getenv("DATABASE_URL", "")

PORT = _int("PORT", 10000)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
USE_WEBHOOK = _bool("USE_WEBHOOK", "true")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "channelrent_hook_secret")

CREDITS_PER_RUPEE = _int("CREDITS_PER_RUPEE", 1)
MIN_TOPUP_CREDITS = _int("MIN_TOPUP_CREDITS", 100)
MIN_WITHDRAWAL_CREDITS = _int("MIN_WITHDRAWAL_CREDITS", 500)
PLATFORM_COMMISSION_PERCENT = _int("PLATFORM_COMMISSION_PERCENT", 20)

BASE_PRICE_PER_POST_CREDITS = _int("BASE_PRICE_PER_POST_CREDITS", 10)
PRICE_PER_1K_SUBSCRIBERS = _float("PRICE_PER_1K_SUBSCRIBERS", 50)
PRICE_PER_100_VIEWS = _float("PRICE_PER_100_VIEWS", 10)
ACTIVITY_MULTIPLIER_HIGH = _float("ACTIVITY_MULTIPLIER_HIGH", 1.5)
ACTIVITY_MULTIPLIER_MEDIUM = _float("ACTIVITY_MULTIPLIER_MEDIUM", 1.0)
ACTIVITY_MULTIPLIER_LOW = _float("ACTIVITY_MULTIPLIER_LOW", 0.6)
MIN_LISTING_PRICE = _int("MIN_LISTING_PRICE", 5)
MAX_LISTING_PRICE = _int("MAX_LISTING_PRICE", 10000)

DELETION_CHECK_INTERVAL_SECONDS = _int("DELETION_CHECK_INTERVAL_SECONDS", 60)
STATS_REFRESH_INTERVAL_HOURS = _int("STATS_REFRESH_INTERVAL_HOURS", 6)

UPI_ID = os.getenv("UPI_ID", "Ancroptics@okicici")
UPI_NAME = os.getenv("UPI_NAME", "Vaibhav pathak")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "Zluextic").lstrip("@")

CONVO_TIMEOUT_SECONDS = 600

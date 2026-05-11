import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
from utils.rate_limiter import allow
from utils.keyboards import main_menu
from utils.formatters import fmt_credits
from database.queries.users import get_user
from database.queries.channels import count_owner_channels

from handlers.common.help import help_cmd, support_panel, referral_panel
from handlers.advertiser.wallet import wallet_panel, txn_history, topup_start
from handlers.advertiser.browse import browse_panel, filters_panel, sort_panel, category_picker, apply_filter
from handlers.advertiser.channel_detail import channel_detail
from handlers.advertiser.my_bookings import my_bookings, view_booking, delete_early_confirm, delete_early_go, cancel_pending
from handlers.owner.dashboard import (my_channels, channel_manage, channel_pause, channel_refresh, channel_remove,
                                      earnings_panel, incoming_bookings, view_owner_booking)
from handlers.admin.dashboard import admin_panel, analytics_panel
from handlers.admin.financial import (finance_panel, topup_list, topup_view, topup_approve, topup_reject,
                                       payout_list, payout_view)
from handlers.admin.user_mgmt import users_panel, user_view, user_ban_toggle
from handlers.admin.channel_mgmt import channels_panel, channel_view as admin_channel_view, channel_suspend
from handlers.admin.booking_mgmt import bookings_panel
from handlers.admin.platform_settings import settings_panel
from handlers.admin.pricing_engine import pricing_panel, pricing_recalc

log = logging.getLogger(__name__)

async def home_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    user = await get_user(u.id)
    n = await count_owner_channels(u.id)
    bal = user["credits_balance"] if user else 0
    earn = user["earnings_pending"] if user else 0
    text = (f"🏪 <b>{config.PLATFORM_NAME}</b>\n\n"
            f"💰 Credits: <b>{fmt_credits(bal)}</b>"
            + (f" | 📈 Earnings: <b>{fmt_credits(earn)}</b>" if n else "")
            + "\n\nChoose an option:")
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu(n>0, u.id in config.SUPERADMIN_IDS))

ROUTES = {
    "home": home_handler,
    "noop": (lambda u,c: u.callback_query.answer()),
    # common
    "common:help": help_cmd,
    "common:support": support_panel,
    "common:ref": referral_panel,
    # advertiser
    "adv:wallet": wallet_panel,
    "adv:txns": txn_history,
    "adv:topup": topup_start,
    "adv:browse": browse_panel,
    "adv:filters": filters_panel,
    "adv:sort": sort_panel,
    "adv:f:cat": category_picker,
    "adv:bookings": my_bookings,
    # owner
    "owner:channels": my_channels,
    "owner:earnings": earnings_panel,
    "owner:bookings": incoming_bookings,
    # admin
    "admin:panel": admin_panel,
    "admin:analytics": analytics_panel,
    "admin:finance": finance_panel,
    "admin:topups": topup_list,
    "admin:payouts": payout_list,
    "admin:users": users_panel,
    "admin:channels": channels_panel,
    "admin:bookings": bookings_panel,
    "admin:settings": settings_panel,
    "admin:pricing": pricing_panel,
    "admin:pricing:recalc": pricing_recalc,
}

PREFIX_ROUTES = [
    ("adv:browse:p:", browse_panel),
    ("adv:f:", apply_filter),
    ("adv:ch:", channel_detail),
    ("adv:bk:del:", delete_early_confirm),
    ("adv:bk:delgo:", delete_early_go),
    ("adv:bk:cancel:", cancel_pending),
    ("adv:bk:", view_booking),
    ("owner:ch:refresh:", channel_refresh),
    ("owner:ch:pause:", channel_pause),
    ("owner:ch:rm:", channel_remove),
    ("owner:ch:", channel_manage),
    ("owner:bk:", view_owner_booking),
    ("admin:topup:ok:", topup_approve),
    ("admin:topup:no:", topup_reject),
    ("admin:topup:", topup_view),
    ("admin:payout:", payout_view),
    ("admin:user:", user_view),
    ("admin:ch:sus:", channel_suspend),
    ("admin:ch:", admin_channel_view),
]

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q: return
    u = q.from_user
    if not allow(u.id):
        await q.answer("⏳ Slow down", show_alert=False); return
    data = q.data or ""
    if data == "noop":
        await q.answer(); return
    fn = ROUTES.get(data)
    if fn:
        try: return await fn(update, context)
        except Exception as e:
            log.exception("router err %s: %s", data, e)
            try: await q.answer("Error", show_alert=True)
            except: pass
            return
    for prefix, fn in PREFIX_ROUTES:
        if data.startswith(prefix):
            try: return await fn(update, context)
            except Exception as e:
                log.exception("router err %s: %s", data, e)
                try: await q.answer("Error", show_alert=True)
                except: pass
                return
    if data.startswith("admin:") and u.id not in config.SUPERADMIN_IDS:
        await q.answer("⛔", show_alert=True); return
    await q.answer()

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
from handlers.start import force_sub_verify
from handlers.advertiser.wallet import wallet_panel, txn_history, topup_start
from handlers.advertiser.browse import browse_panel, filters_panel, sort_panel, category_picker, apply_filter
from handlers.advertiser.channel_detail import channel_detail, report_start
from handlers.advertiser.my_bookings import my_bookings, view_booking, delete_early_confirm, delete_early_go, cancel_pending
from handlers.advertiser.rating import submit_rating
from handlers.owner.dashboard import (my_channels, channel_manage, channel_pause, channel_refresh, channel_remove,
                                      earnings_panel, incoming_bookings, view_owner_booking)
from handlers.admin.dashboard import admin_panel, analytics_panel
from handlers.admin.financial import (finance_panel, topup_list, topup_view, topup_approve, topup_reject,
                                       payout_list, payout_view)
from handlers.admin.user_mgmt import users_panel, user_view, user_ban_toggle
from handlers.admin.channel_mgmt import channels_panel, channel_view as admin_channel_view, channel_suspend
from handlers.admin.booking_mgmt import bookings_panel
from handlers.admin.platform_settings import settings_panel, pricing_settings_panel, forcesub_panel
from handlers.admin.pricing_engine import pricing_panel, pricing_recalc

log = logging.getLogger(__name__)

async def home_handler(update, context):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass
    u = q.from_user
    try:
        user = await get_user(u.id)
        n = await count_owner_channels(u.id)
    except Exception:
        log.exception("home_handler load failed")
        user, n = None, 0
    bal = user["credits_balance"] if user else 0
    earn = user["earnings_pending"] if user else 0
    text = (f"\U0001f3ea <b>{config.PLATFORM_NAME}</b>\n\n"
            f"\U0001f4b0 Credits: <b>{fmt_credits(bal)}</b>"
            + (f" | \U0001f4c8 Earnings: <b>{fmt_credits(earn)}</b>" if n else "")
            + "\n\nChoose an option:")
    markup = main_menu(n>0, u.id in config.SUPERADMIN_IDS)
    try:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        log.warning("home edit failed: %s", e)
        try:
            await context.bot.send_message(q.message.chat_id, text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass

ROUTES = {
    "home": home_handler,
    "noop": (lambda u,c: u.callback_query.answer()),
    "common:help": help_cmd,
    "common:support": support_panel,
    "common:ref": referral_panel,
    "adv:wallet": wallet_panel,
    "adv:txns": txn_history,
    "adv:topup": topup_start,
    "adv:browse": browse_panel,
    "adv:filters": filters_panel,
    "adv:sort": sort_panel,
    "adv:f:cat": category_picker,
    "adv:bookings": my_bookings,
    "owner:channels": my_channels,
    "owner:earnings": earnings_panel,
    "owner:bookings": incoming_bookings,
    "admin:panel": admin_panel,
    "admin:analytics": analytics_panel,
    "admin:finance": finance_panel,
    "admin:topups": topup_list,
    "admin:payouts": payout_list,
    "admin:users": users_panel,
    "admin:channels": channels_panel,
    "admin:bookings": bookings_panel,
    "admin:settings": settings_panel,
    "admin:settings:price": pricing_settings_panel,
    "admin:settings:forcesub": forcesub_panel,
    "common:fsub:verify": force_sub_verify,
    "admin:pricing": pricing_panel,
    "admin:pricing:recalc": pricing_recalc,
}

PREFIX_ROUTES = [
    ("adv:browse:p:", browse_panel),
    ("adv:f:", apply_filter),
    ("adv:ch:", channel_detail),
    ("adv:report:", report_start),
    ("adv:rate:", submit_rating),
    ("adv:bk:del:", delete_early_confirm),
    ("adv:bk:delgo:", delete_early_go),
    ("adv:bk:cancel:", cancel_pending),
    ("adv:bk:", view_booking),
    ("owner:ch:refresh:", channel_refresh),
    ("owner:ch:pause:", channel_pause),
    ("owner:ch:rm:", channel_remove),
    ("owner:ch:", channel_manage),
    ("owner:bk:", view_owner_booking),
    ("admin:users:p:", users_panel),
    ("admin:topup:ok:", topup_approve),
    ("admin:topup:no:", topup_reject),
    ("admin:topup:", topup_view),
    ("admin:payout:", payout_view),
    ("admin:user:", user_view),
    ("admin:ch:sus:", channel_suspend),
    ("admin:ch:", admin_channel_view),
]

async def callback_router(update, context):
    q = update.callback_query
    if not q: return
    u = q.from_user
    if not allow(u.id):
        await q.answer("\u23f3 Slow down", show_alert=False); return
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
        await q.answer("\u26d4", show_alert=True); return
    await q.answer()

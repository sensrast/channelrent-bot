import asyncio
import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from aiohttp import web

import config
from database.pool import init_pool, close_pool, db
from services.scheduler_service import start as start_sched, stop as stop_sched
from services.health_server import build_app
from services.notification_service import notify_superadmin

from handlers.start import start_handler, universal_cancel
from handlers.common.help import help_cmd
from handlers.callbacks import callback_router
from handlers.advertiser.wallet import build_topup_conv
from handlers.advertiser.booking_flow import build_booking_conv
from handlers.owner.channel_setup import build_setup_conv
from handlers.owner.booking_mgmt import build_reject_conv, approve_booking
from handlers.owner.earnings import build_payout_conv
from handlers.admin.financial import build_payout_admin_conv
from handlers.admin.user_mgmt import build_user_admin_conv
from handlers.admin.platform_settings import build_settings_conv
from handlers.admin.broadcast import build_bcast_conv
from handlers.admin.platform_settings import toggle_setting
from handlers.admin.pricing_engine import build_pricing_conv
from handlers.admin.dashboard import admin_panel
from handlers.advertiser.my_bookings import my_bookings
from handlers.advertiser.browse import browse_panel
from handlers.owner.dashboard import my_channels

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout)
log = logging.getLogger("main")

async def _post_init(app: Application):
    await init_pool()
    start_sched(app.bot)
    log.info("DB + scheduler ready")
    try:
        from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
        public_cmds = [
            BotCommand("start","Open the main menu"),
            BotCommand("help","How it works"),
            BotCommand("wallet","Open your wallet"),
            BotCommand("bookings","View your bookings"),
            BotCommand("channels","Manage your channels"),
            BotCommand("browse","Browse channels"),
            BotCommand("cancel","Cancel current action"),
        ]
        await app.bot.set_my_commands(public_cmds, scope=BotCommandScopeDefault())
        for sid in config.SUPERADMIN_IDS:
            try:
                await app.bot.set_my_commands(public_cmds + [BotCommand("admin","Open admin panel")], scope=BotCommandScopeChat(chat_id=sid))
            except Exception as e:
                log.warning("admin commands set failed for %s: %s", sid, e)
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)
    try:
        await notify_superadmin(app.bot, f"🟢 {config.PLATFORM_NAME} started.")
    except Exception as e:
        log.warning("notify start failed: %s", e)

async def _post_shutdown(app: Application):
    stop_sched()
    await close_pool()

def build_app_obj():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set")
    app = Application.builder().token(config.BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build()

    app.add_handler(build_setup_conv())
    app.add_handler(build_booking_conv())
    app.add_handler(build_topup_conv())
    app.add_handler(build_payout_conv())
    app.add_handler(build_reject_conv())
    app.add_handler(build_payout_admin_conv())
    app.add_handler(build_user_admin_conv())
    app.add_handler(build_settings_conv())
    app.add_handler(build_bcast_conv())
    app.add_handler(build_pricing_conv())
    from telegram.ext import CallbackQueryHandler as _CQH
    app.add_handler(_CQH(toggle_setting, pattern=r"^admin:tog:[a-z_]+$"))

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("wallet", lambda u,c: u.message.reply_text("Open /start menu → 💰 My Wallet")))
    app.add_handler(CommandHandler("bookings", lambda u,c: u.message.reply_text("Open /start menu → 📋 My Bookings")))
    app.add_handler(CommandHandler("channels", lambda u,c: u.message.reply_text("Open /start menu → 📢 My Channels")))
    app.add_handler(CommandHandler("browse", lambda u,c: u.message.reply_text("Open /start menu → 🔍 Browse Channels")))
    app.add_handler(CommandHandler("cancel", universal_cancel))

    app.add_handler(CallbackQueryHandler(callback_router))

    async def err_handler(update, context):
        log.exception("Unhandled: %s", context.error)
    app.add_error_handler(err_handler)

    return app

async def run_webhook(app: Application):
    await app.initialize()
    await app.start()
    url = f"{config.WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(url=url, secret_token=config.WEBHOOK_SECRET, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    log.info("Webhook set: %s", url)
    aio = build_app(app)
    runner = web.AppRunner(aio)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    log.info("HTTP listening on %s", config.PORT)
    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        await runner.cleanup()
        await app.stop()
        await app.shutdown()

async def run_polling(app: Application):
    await app.initialize()
    aio = build_app(app)
    runner = web.AppRunner(aio); await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT); await site.start()
    log.info("HTTP listening on %s (polling mode)", config.PORT)
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()

def main():
    app = build_app_obj()
    if config.USE_WEBHOOK and config.WEBHOOK_URL :
        asyncio.run(run_webhook(app))
    else:
        asyncio.run(run_polling(app))

if __name__ == "__main__":
    main()

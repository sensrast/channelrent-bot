"""ChannelRent Bot entry point."""
import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

import config
from database.pool import init_pool, close_pool, run_migrations
from services.scheduler_service import start_scheduler, stop_scheduler
from services.health_server import start_health_server
from handlers.start import start_handler
from handlers.callbacks import callback_router
from handlers.admin.dashboard import admin_panel_handler
from handlers.common.help import help_handler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)


async def on_startup(app):
    logger.info('Connecting DB...')
    await init_pool(config.DATABASE_URL)
    await run_migrations()
    start_scheduler(app.bot)
    await start_health_server(app, config.PORT)
    logger.info('ChannelRent started')
    for admin_id in config.SUPERADMIN_IDS:
        try:
            await app.bot.send_message(admin_id, 'ChannelRent bot started')
        except Exception as e:
            logger.warning(f'admin notify failed: {e}')


async def on_shutdown(app):
    stop_scheduler()
    await close_pool()


def main():
    if not config.BOT_TOKEN:
        logger.error('BOT_TOKEN missing')
        sys.exit(1)
    app = Application.builder().token(config.BOT_TOKEN).post_init(on_startup).post_shutdown(on_shutdown).build()
    app.add_handler(CommandHandler('start', start_handler))
    app.add_handler(CommandHandler('admin', admin_panel_handler))
    app.add_handler(CommandHandler('help', help_handler))
    app.add_handler(CallbackQueryHandler(callback_router))
    if config.USE_WEBHOOK and config.WEBHOOK_URL:
        app.run_webhook(listen='0.0.0.0', port=config.PORT, url_path=config.BOT_TOKEN, webhook_url=f'{config.WEBHOOK_URL}/{config.BOT_TOKEN}', allowed_updates=Update.ALL_TYPES)
    else:
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

import logging
import time
from aiohttp import web
from telegram import Update
import config
from database.pool import db
from database.queries.bookings import count_active_bookings

log = logging.getLogger(__name__)
START = time.time()

def build_app(application):
    app = web.Application()

    async def health(request):
        try:
            ok = await db.fetchval("SELECT 1")
            db_ok = ok == 1
        except Exception:
            db_ok = False
        try:
            active = await count_active_bookings()
        except Exception:
            active = -1
        return web.json_response({
            "status": "running",
            "uptime": int(time.time() - START),
            "active_bookings": active,
            "scheduler_running": True,
            "db_connected": db_ok,
        })

    async def root(request):
        return web.Response(text=f"{config.PLATFORM_NAME} bot is running.")

    async def webhook(request):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != config.WEBHOOK_SECRET:
            return web.Response(status=403, text="forbidden")
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="ok")

    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    app.router.add_post(f"/webhook", webhook)
    return app

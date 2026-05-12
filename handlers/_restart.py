from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

async def restart_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()
    except Exception:
        pass
    from handlers.start import start_handler
    try:
        await start_handler(update, context)
    except Exception:
        pass
    return ConversationHandler.END

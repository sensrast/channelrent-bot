"""Universal conversation fallback that ends the conversation AND actually
navigates the user to the requested screen.

The original bot used ``CallbackQueryHandler(lambda u,c: ConversationHandler.END, ...)``
or a no-op ``_univ_cancel`` as the only callback fallback for many
``ConversationHandler``s. That silently ends the conversation but does NOT
render the target Back/Cancel screen, so users see "nothing happens" when
pressing Back or Cancel while a conversation is active.

This helper builds a fallback handler that:
    1. Ends the active conversation.
    2. Dispatches the callback through the regular ``callback_router`` so the
       Back/Cancel destination screen actually appears.
"""
from telegram.ext import CallbackQueryHandler, ConversationHandler

NAV_PATTERN = (
    r"^("
    r"home"
    r"|adv:(wallet|topup|browse|bookings|txns|filters|sort)"
    r"|adv:topup(:custom)?"
    r"|adv:ch:\d+"
    r"|adv:bk:\d+"
    r"|owner:(channels|earnings|bookings|payout|add)"
    r"|owner:ch:\d+"
    r"|admin:(panel|analytics|finance|topups|payouts|users|channels|bookings|pricing|bcast|adpost)"
    r"|admin:settings(:price|:forcesub|:joinreq)?"
    r"|admin:user:\d+"
    r"|admin:ch:\d+"
    r"|common:(help|support|ref)"
    r")$"
)


async def _route_and_end(update, context):
    try:
        context.user_data.pop("set_key", None)
    except Exception:
        pass
    try:
        from handlers.callbacks import callback_router
        await callback_router(update, context)
    except Exception:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
    return ConversationHandler.END


def nav_fallback(pattern: str = NAV_PATTERN) -> CallbackQueryHandler:
    """Return a CallbackQueryHandler suitable for ConversationHandler.fallbacks
    that routes Back/Cancel callbacks through the global router."""
    return CallbackQueryHandler(_route_and_end, pattern=pattern)

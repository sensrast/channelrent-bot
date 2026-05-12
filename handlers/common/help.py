import config
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import kb, back
from database.pool import db

HELP_TEXT = (
"❓ <b>How ChannelRent Works</b>\n\n"
"<b>For Advertisers</b>\n"
"1. Top up credits (₹1 = 1 credit)\n"
"2. Browse channels and pick one\n"
"3. Send your ad content\n"
"4. Pay in credits — ad goes live\n"
"5. Bot auto-deletes when time expires\n\n"
"<b>For Channel Owners</b>\n"
"1. Add @{bot} as admin to your channel\n"
"2. List your channel (set rules + price)\n"
"3. Earn credits per booking\n"
"4. Withdraw via UPI anytime above 500 credits\n\n"
"<b>Refund Policy</b>\n"
"• Early deletion by advertiser → pro-rata refund\n"
"• Owner deletes early → 100% refund to advertiser\n"
"• Rejected booking → 100% refund instantly\n\n"
f"Support: @{config.SUPPORT_USERNAME}"
).replace("{bot}", config.BOT_USERNAME)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode="HTML")
    elif update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(HELP_TEXT, parse_mode="HTML", reply_markup=kb([back("home")]))

async def support_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"🎫 <b>Support</b>\n\nContact: @{config.SUPPORT_USERNAME}\n\nFor faster help, include your booking reference."
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb([back("home")]))

async def referral_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = update.effective_user
    try:
        bonus = int(float(await db.fetchval("SELECT value FROM platform_settings WHERE key='referral_bonus_credits'") or 50))
    except Exception:
        bonus = 50
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{u.id}"
    txt = (f"🔗 <b>Refer & Earn</b>\n\n"
           f"Share your link. When a friend joins, you get <b>{bonus} credits</b>!\n\n"
           f"Your link:\n<code>{link}</code>")
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb([back("home")]))

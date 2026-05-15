import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters
import config
from utils.decorators import superadmin_only
from utils.keyboards import kb, back
from utils.validators import parse_buttons
from database.queries.channels import list_owner_channels, list_all_verified

log = logging.getLogger(__name__)

(AP_PICK_LIST, AP_PICK_CHANNELS, AP_GET_CONTENT, AP_ASK_BUTTONS,
 AP_GET_BUTTONS, AP_ASK_PIN, AP_ASK_DELETE, AP_CONFIRM) = range(8)

PAGE_SIZE = 10

DELETE_PRESETS = [
    ("1 hour", 60),
    ("6 hours", 6 * 60),
    ("12 hours", 12 * 60),
    ("24 hours", 24 * 60),
    ("3 days", 3 * 24 * 60),
    ("7 days", 7 * 24 * 60),
]


def _state(context):
    if "admin_post" not in context.user_data:
        context.user_data["admin_post"] = {
            "list_type": None,
            "channels": [],
            "selected": set(),
            "page": 0,
            "content_type": None,
            "content_text": None,
            "media_file_id": None,
            "caption": None,
            "buttons": None,
            "pin": False,
            "auto_delete_minutes": None,
        }
    return context.user_data["admin_post"]


def _clear(context):
    context.user_data.pop("admin_post", None)


async def _load_channels(list_type, admin_id):
    if list_type == "mine":
        rows = await list_owner_channels(admin_id)
    else:
        rows = await list_all_verified()
    out = []
    for r in rows:
        out.append({
            "channel_id": r["channel_id"],
            "title": r["title"],
            "telegram_chat_id": r["telegram_chat_id"],
        })
    return out


@superadmin_only
async def adpost_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _clear(context)
    _state(context)
    txt = ("📣 <b>Post Ad to Channels</b>\n\n"
           "Choose which list to pick channels from:")
    rows = [
        [("📢 My Channels", "admin:adpost:list:mine")],
        [("🌐 All Channels", "admin:adpost:list:all")],
        [("❌ Cancel", "admin:adpost:cancel")],
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return AP_PICK_LIST


async def adpost_pick_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":cancel"):
        _clear(context)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("admin:panel")]))
        return ConversationHandler.END
    list_type = q.data.split(":")[-1]
    s = _state(context)
    s["list_type"] = list_type
    s["channels"] = await _load_channels(list_type, q.from_user.id)
    s["selected"] = set()
    s["page"] = 0
    if not s["channels"]:
        await q.edit_message_text("No channels found in this list.",
                                  reply_markup=kb([[("🔙 Back", "admin:adpost")], back("admin:panel")]))
        return AP_PICK_LIST
    await _render_channels(q, context)
    return AP_PICK_CHANNELS


async def _render_channels(q, context):
    s = _state(context)
    chans = s["channels"]
    total = len(chans)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if s["page"] >= pages:
        s["page"] = pages - 1
    start = s["page"] * PAGE_SIZE
    page_items = chans[start:start + PAGE_SIZE]
    rows = []
    for c in page_items:
        cid = c["channel_id"]
        mark = "✅" if cid in s["selected"] else "⬜"
        title = (c["title"] or "—")[:40]
        rows.append([(f"{mark} {title}", f"admin:adpost:tog:{cid}")])
    nav = []
    if s["page"] > 0:
        nav.append(("◀️ Prev", "admin:adpost:pg:prev"))
    nav.append((f"Page {s['page']+1}/{pages}", "noop"))
    if s["page"] < pages - 1:
        nav.append(("Next ▶️", "admin:adpost:pg:next"))
    rows.append(nav)
    all_selected = len(s["selected"]) == total and total > 0
    rows.append([
        ("☑️ Unselect All" if all_selected else "✅ Select All", "admin:adpost:selall"),
        ("🧹 Clear", "admin:adpost:clr"),
    ])
    rows.append([(f"➡️ Next ({len(s['selected'])} selected)", "admin:adpost:next")])
    rows.append([("❌ Cancel", "admin:adpost:cancel")])
    label = "📢 My Channels" if s["list_type"] == "mine" else "🌐 All Channels"
    txt = (f"<b>{label}</b>\n"
           f"Total: {total} • Selected: {len(s['selected'])}\n\n"
           f"Tap a channel to toggle. Use Select All to pick everything.")
    try:
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    except Exception as e:
        log.debug("render channels edit failed: %s", e)


async def adpost_channels_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    s = _state(context)
    data = q.data
    if data == "admin:adpost:cancel":
        _clear(context)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("admin:panel")]))
        return ConversationHandler.END
    if data == "admin:adpost:pg:prev":
        s["page"] = max(0, s["page"] - 1)
    elif data == "admin:adpost:pg:next":
        s["page"] = s["page"] + 1
    elif data == "admin:adpost:selall":
        all_ids = {c["channel_id"] for c in s["channels"]}
        if s["selected"] == all_ids:
            s["selected"] = set()
        else:
            s["selected"] = all_ids
    elif data == "admin:adpost:clr":
        s["selected"] = set()
    elif data.startswith("admin:adpost:tog:"):
        cid = int(data.split(":")[-1])
        if cid in s["selected"]:
            s["selected"].discard(cid)
        else:
            s["selected"].add(cid)
    elif data == "admin:adpost:next":
        if not s["selected"]:
            await q.answer("Select at least one channel", show_alert=True)
            return AP_PICK_CHANNELS
        await q.edit_message_text(
            "📤 <b>Send Your Ad Content</b>\n\n"
            "Send text (with links), a photo, or a document.\n"
            "❌ No videos, GIFs, MP4s, stickers, voice or audio.\n\n"
            "Send /cancel to abort.",
            parse_mode="HTML")
        return AP_GET_CONTENT
    await _render_channels(q, context)
    return AP_PICK_CHANNELS


async def adpost_get_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    s = _state(context)
    if m.video or m.animation or m.sticker or m.video_note or m.voice or m.audio:
        await m.reply_text("❌ Videos, GIFs, stickers, voice and audio are not allowed.")
        return AP_GET_CONTENT
    if m.photo:
        s["content_type"] = "photo"
        s["media_file_id"] = m.photo[-1].file_id
        s["caption"] = m.caption or ""
    elif m.document:
        s["content_type"] = "document"
        s["media_file_id"] = m.document.file_id
        s["caption"] = m.caption or ""
    elif m.text:
        s["content_type"] = "text"
        s["content_text"] = m.text
    else:
        await m.reply_text("Unsupported content. Send text, photo, or document.")
        return AP_GET_CONTENT
    rows = [[("✅ Yes", "admin:adpost:btn:yes"), ("❌ No", "admin:adpost:btn:no")]]
    await m.reply_text("Add inline URL buttons?", reply_markup=kb(rows))
    return AP_ASK_BUTTONS


async def adpost_ask_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":no"):
        return await _ask_pin(q, context)
    await q.edit_message_text(
        "Send buttons one per line:\n<code>Label - https://url</code>\n\nMax 5 buttons.",
        parse_mode="HTML")
    return AP_GET_BUTTONS


async def adpost_get_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = parse_buttons(update.message.text)
    if not btns:
        await update.message.reply_text("Invalid format. Try again or /cancel.")
        return AP_GET_BUTTONS
    s = _state(context)
    s["buttons"] = btns
    return await _ask_pin(update.message, context)


async def _ask_pin(target, context):
    txt = ("📌 <b>Pin the message in each channel?</b>\n\n"
           "Pinned messages stay at the top of every channel until removed.")
    rows = [[("📌 Yes, pin it", "admin:adpost:pin:yes"),
             ("➖ No, don't pin", "admin:adpost:pin:no")],
            [("❌ Cancel", "admin:adpost:cancel")]]
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    else:
        await target.reply_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return AP_ASK_PIN


async def adpost_ask_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":cancel"):
        _clear(context)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("admin:panel")]))
        return ConversationHandler.END
    s = _state(context)
    s["pin"] = q.data.endswith(":yes")
    return await _ask_delete(q, context)


async def _ask_delete(q, context):
    txt = ("🗑 <b>Auto-delete the message?</b>\n\n"
           "Pick a duration after which the post (and its pin) will be removed automatically.\n"
           "Choose <b>Never</b> to keep it permanently.")
    rows = []
    line = []
    for label, mins in DELETE_PRESETS:
        line.append((f"⏱ {label}", f"admin:adpost:del:{mins}"))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([("♾ Never (keep)", "admin:adpost:del:0")])
    rows.append([("❌ Cancel", "admin:adpost:cancel")])
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return AP_ASK_DELETE


async def adpost_ask_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":cancel"):
        _clear(context)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("admin:panel")]))
        return ConversationHandler.END
    s = _state(context)
    try:
        mins = int(q.data.split(":")[-1])
    except Exception:
        mins = 0
    s["auto_delete_minutes"] = mins if mins > 0 else None
    return await _show_confirm(q, context)


def _human_duration(minutes):
    if not minutes:
        return "Never"
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes / 60
    if hours < 24:
        h = int(hours) if hours == int(hours) else round(hours, 1)
        return f"{h} hour" + ("s" if h != 1 else "")
    days = hours / 24
    d = int(days) if days == int(days) else round(days, 1)
    return f"{d} day" + ("s" if d != 1 else "")


async def _show_confirm(target, context):
    s = _state(context)
    sel = len(s["selected"])
    btn_preview = ""
    if s["buttons"]:
        btn_preview = "\n🔘 Buttons: " + ", ".join(x[0] for x in s["buttons"])
    pin_label = "📌 Yes" if s.get("pin") else "➖ No"
    del_label = _human_duration(s.get("auto_delete_minutes"))
    txt = (f"📋 <b>Confirm Broadcast</b>\n\n"
           f"Channels selected: <b>{sel}</b>\n"
           f"Content: {s['content_type']}"
           f"{btn_preview}\n"
           f"Pin: <b>{pin_label}</b>\n"
           f"Auto-delete: <b>{del_label}</b>\n\n"
           f"💎 No credits will be charged. (Admin broadcast)")
    rows = [[("✅ Confirm & Send", "admin:adpost:confirm"), ("❌ Cancel", "admin:adpost:cancel")]]
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    else:
        await target.reply_text(txt, parse_mode="HTML", reply_markup=kb(rows))
    return AP_CONFIRM


def _build_markup(buttons):
    if not buttons:
        return None
    try:
        rows = [[InlineKeyboardButton(label, url=url) for label, url in buttons]]
        return InlineKeyboardMarkup(rows)
    except Exception:
        return None


async def _safe_pin(bot, chat_id, message_id):
    try:
        await bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=True)
    except Exception as e:
        log.debug("adpost pin skipped for %s/%s: %s", chat_id, message_id, e)
        return False
    await asyncio.sleep(0.6)
    for delta in (1, 2, 3, 4, 5):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id + delta)
        except Exception:
            pass
    return True


async def _delayed_delete(bot, chat_id, message_id, delay_seconds):
    try:
        await asyncio.sleep(delay_seconds)
    except asyncio.CancelledError:
        return
    try:
        try:
            await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        log.debug("adpost auto-delete failed for %s/%s: %s", chat_id, message_id, e)


async def adpost_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.endswith(":cancel"):
        _clear(context)
        await q.edit_message_text("❌ Cancelled.", reply_markup=kb([back("admin:panel")]))
        return ConversationHandler.END
    s = _state(context)
    selected_ids = list(s["selected"])
    chans_by_id = {c["channel_id"]: c for c in s["channels"]}
    markup = _build_markup(s["buttons"])
    do_pin = bool(s.get("pin"))
    auto_min = s.get("auto_delete_minutes")
    sent, failed, pinned = 0, 0, 0
    fail_titles = []
    await q.edit_message_text(f"📤 Sending to {len(selected_ids)} channels...")
    for cid in selected_ids:
        c = chans_by_id.get(cid)
        if not c:
            failed += 1
            continue
        try:
            chat_id = c["telegram_chat_id"]
            if s["content_type"] == "text":
                msg = await context.bot.send_message(chat_id, s["content_text"], reply_markup=markup,
                                                     disable_web_page_preview=False)
            elif s["content_type"] == "photo":
                msg = await context.bot.send_photo(chat_id, s["media_file_id"],
                                                   caption=s["caption"] or None, reply_markup=markup)
            elif s["content_type"] == "document":
                msg = await context.bot.send_document(chat_id, s["media_file_id"],
                                                      caption=s["caption"] or None, reply_markup=markup)
            else:
                failed += 1
                continue
            sent += 1
            if do_pin:
                ok = await _safe_pin(context.bot, chat_id, msg.message_id)
                if ok:
                    pinned += 1
            if auto_min:
                try:
                    asyncio.create_task(_delayed_delete(context.bot, chat_id, msg.message_id, auto_min * 60))
                except Exception as e:
                    log.warning("schedule auto-delete failed for %s: %s", chat_id, e)
        except Exception as e:
            log.warning("adpost send failed for %s: %s", cid, e)
            failed += 1
            if c and c.get("title") and len(fail_titles) < 10:
                fail_titles.append(c["title"])
        await asyncio.sleep(0.05)
    summary_lines = [
        f"✅ Sent: {sent}",
        f"❌ Failed: {failed}",
    ]
    if do_pin:
        summary_lines.append(f"📌 Pinned: {pinned}")
    if auto_min:
        summary_lines.append(f"🗑 Auto-delete in: {_human_duration(auto_min)}")
    summary = "\n".join(summary_lines)
    if fail_titles:
        summary += "\n\nFailed channels:\n• " + "\n• ".join(fail_titles)
    await context.bot.send_message(q.message.chat_id, summary, reply_markup=kb([back("admin:panel")]))
    _clear(context)
    return ConversationHandler.END


async def _cancel_cmd(update, context):
    _clear(context)
    if update.message:
        await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def build_adpost_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(adpost_start, pattern=r"^admin:adpost$")],
        states={
            AP_PICK_LIST: [CallbackQueryHandler(adpost_pick_list,
                                                pattern=r"^admin:adpost:(list:(mine|all)|cancel)$")],
            AP_PICK_CHANNELS: [CallbackQueryHandler(adpost_channels_action,
                                                    pattern=r"^admin:adpost:(tog:-?\d+|pg:(prev|next)|selall|clr|next|cancel)$")],
            AP_GET_CONTENT: [MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.ANIMATION
                 | filters.Sticker.ALL | filters.AUDIO | filters.VOICE | filters.VIDEO_NOTE)
                & ~filters.COMMAND, adpost_get_content)],
            AP_ASK_BUTTONS: [CallbackQueryHandler(adpost_ask_buttons,
                                                  pattern=r"^admin:adpost:btn:(yes|no)$")],
            AP_GET_BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, adpost_get_buttons)],
            AP_ASK_PIN: [CallbackQueryHandler(adpost_ask_pin,
                                              pattern=r"^admin:adpost:(pin:(yes|no)|cancel)$")],
            AP_ASK_DELETE: [CallbackQueryHandler(adpost_ask_delete,
                                                 pattern=r"^admin:adpost:(del:\d+|cancel)$")],
            AP_CONFIRM: [CallbackQueryHandler(adpost_confirm,
                                              pattern=r"^admin:adpost:(confirm|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", _cancel_cmd)],
        conversation_timeout=config.CONVO_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, per_message=False,
        allow_reentry=True,
    )

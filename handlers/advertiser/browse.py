from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import kb, back, pagination
from utils.formatters import fmt_credits, activity_emoji, fmt_subs_short
from database.queries.channels import list_marketplace, count_marketplace, list_all_categories

PAGE_SIZE = 5

def _filters(context):
    f = context.user_data.setdefault("browse_filters", {"category_id":None,"tier":None,"budget":None,"min_subs":None,"sort":"rating"})
    return f

def _parse_page(q):
    data = q.data or ""
    if data.startswith("adv:browse:p:"):
        try:
            return int(data.split(":")[3])
        except Exception:
            return 0
    return 0

async def browse_panel(update, context, page=None):
    q = update.callback_query
    await q.answer()
    if page is None:
        page = _parse_page(q)
    f = _filters(context)
    rows = await list_marketplace(f["category_id"], f["tier"], f["budget"], f["min_subs"], f["sort"], offset=page*PAGE_SIZE, limit=PAGE_SIZE)
    total = await count_marketplace(f["category_id"], f["tier"], f["budget"], f["min_subs"])
    pages = max(1, (total + PAGE_SIZE - 1)//PAGE_SIZE)
    head = f"🔍 <b>Browse Channels</b> ({total} found)\n\n"
    if not rows:
        head += "No channels match. Try changing filters."
    body = ""
    for c in rows:
        cat = c.get("category_emoji","📂")
        body += (f"\n━━━━━━━━━━━━━━━━━\n{cat} <b>{c['title']}</b>\n"
                 f"👥 {fmt_credits(c['subscriber_count'])} subs • {activity_emoji(c['activity_tier'])} {c['activity_tier'].upper()}\n"
                 f"💰 <b>{c['final_price_credits']} cr/hr</b> • ⭐ {c['rating']:.1f} ({c['rating_count']})\n")
    kbrows = []
    for c in rows:
        title = c['title'][:22]
        subs_label = fmt_subs_short(c.get('subscriber_count') or 0)
        kbrows.append([(f"📋 {title} ({subs_label})", f"adv:ch:{c['channel_id']}")])
    kbrows.append([("🎛️ Filters","adv:filters"),("🔁 Sort","adv:sort")])
    pgrow = []
    if page > 0: pgrow.append(("◀️ Prev", f"adv:browse:p:{page-1}"))
    pgrow.append((f"{page+1}/{pages}", "noop"))
    if page < pages-1: pgrow.append(("Next ▶️", f"adv:browse:p:{page+1}"))
    kbrows.append(pgrow)
    kbrows.append(back("home"))
    await q.edit_message_text(head + body, parse_mode="HTML", reply_markup=kb(kbrows))

async def filters_panel(update, context):
    q = update.callback_query
    await q.answer()
    f = _filters(context)
    cats = await list_all_categories()
    cat_label = "All"
    if f["category_id"]:
        for c in cats:
            if c["category_id"] == f["category_id"]: cat_label = f"{c['emoji']} {c['name']}"
    tier_label = (f["tier"] or "All").upper()
    budget_label = f["budget"] or "Any"
    subs_label = f["min_subs"] or "Any"
    txt = (f"🎛️ <b>Filters</b>\n\nCategory: <b>{cat_label}</b>\nActivity: <b>{tier_label}</b>\n"
           f"Budget (max cr/hr): <b>{budget_label}</b>\nMin Subscribers: <b>{subs_label}</b>")
    rows = [
        [("📂 Category","adv:f:cat")],
        [("⚡ Activity: All","adv:f:t:none"),("🔥 HIGH","adv:f:t:high")],
        [("⚡ MEDIUM","adv:f:t:medium"),("🌱 LOW","adv:f:t:low")],
        [("💰 <100","adv:f:b:100"),("100-500","adv:f:b:500")],
        [("500-1000","adv:f:b:1000"),("Any","adv:f:b:none")],
        [("👥 1K+","adv:f:s:1000"),("10K+","adv:f:s:10000"),("100K+","adv:f:s:100000")],
        [("🔄 Reset","adv:f:reset")],
        back("adv:browse"),
    ]
    await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb(rows))

async def sort_panel(update, context):
    q = update.callback_query
    await q.answer()
    rows = [
        [("⭐ Rating","adv:f:srt:rating")],
        [("💰 Price ↑","adv:f:srt:price_asc"),("💰 Price ↓","adv:f:srt:price_desc")],
        [("👥 Subscribers","adv:f:srt:subs"),("⚡ Activity","adv:f:srt:activity")],
        back("adv:browse"),
    ]
    await q.edit_message_text("🔁 <b>Sort By</b>", parse_mode="HTML", reply_markup=kb(rows))

async def category_picker(update, context):
    q = update.callback_query
    await q.answer()
    cats = await list_all_categories()
    rows = [[("All Categories","adv:f:c:none")]]
    cur = []
    for c in cats:
        cur.append((f"{c['emoji']} {c['name']}", f"adv:f:c:{c['category_id']}"))
        if len(cur)==2: rows.append(cur); cur=[]
    if cur: rows.append(cur)
    rows.append(back("adv:filters"))
    await q.edit_message_text("📂 <b>Pick Category</b>", parse_mode="HTML", reply_markup=kb(rows))

async def apply_filter(update, context):
    q = update.callback_query
    await q.answer("Applied")
    data = q.data
    f = _filters(context)
    parts = data.split(":")
    kind = parts[2]; val = parts[3] if len(parts) > 3 else None
    if kind == "reset":
        context.user_data["browse_filters"] = {"category_id":None,"tier":None,"budget":None,"min_subs":None,"sort":"rating"}
    elif kind == "c":
        f["category_id"] = None if val == "none" else int(val)
    elif kind == "t":
        f["tier"] = None if val == "none" else val
    elif kind == "b":
        f["budget"] = None if val == "none" else int(val)
    elif kind == "s":
        f["min_subs"] = int(val)
    elif kind == "srt":
        f["sort"] = val
    await filters_panel(update, context) if kind in ("c","reset") else await browse_panel(update, context, page=0)

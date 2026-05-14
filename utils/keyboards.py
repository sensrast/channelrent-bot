from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=cd) for t, cd in row] for row in rows])

def kb_url(rows):
    out = []
    for row in rows:
        rr = []
        for item in row:
            if len(item) == 3 and item[2] == "url":
                rr.append(InlineKeyboardButton(item[0], url=item[1]))
            else:
                rr.append(InlineKeyboardButton(item[0], callback_data=item[1]))
        out.append(rr)
    return InlineKeyboardMarkup(out)

def back(cd):
    return [("🔙 Back", cd)]

def main_menu(has_channels: bool, is_admin: bool):
    if has_channels:
        rows = [
            [("📢 My Channels","owner:channels"),("📊 My Earnings","owner:earnings")],
            [("➕ Add Channel","owner:add"),("📋 Incoming Bookings","owner:bookings")],
            [("🔍 Browse Channels","adv:browse"),("📋 My Bookings","adv:bookings")],
            [("💰 My Wallet","adv:wallet"),("➕ Top Up","adv:topup")],
            [("🔗 Referral","common:ref"),("❓ Help","common:help")],
            [("🎫 Support","common:support")],
        ]
    else:
        rows = [
            [("🔍 Browse Channels","adv:browse"),("📋 My Bookings","adv:bookings")],
            [("💰 My Wallet","adv:wallet"),("➕ Top Up","adv:topup")],
            [("➕ List My Channel","owner:add")],
            [("🔗 Referral","common:ref"),("❓ How It Works","common:help")],
            [("🎫 Support","common:support")],
        ]
    if is_admin:
        rows.append([("👑 Admin Panel","admin:panel")])
    return kb(rows)

def yes_no(yes_cd, no_cd, yes="✅ Yes", no="❌ No"):
    return kb([[(yes, yes_cd),(no, no_cd)]])

def pagination(prefix, page, total_pages, back_cd=None):
    row = []
    if page > 0: row.append(("◀️ Prev", f"{prefix}:p:{page-1}"))
    row.append((f"Page {page+1}/{max(total_pages,1)}", "noop"))
    if page < total_pages - 1: row.append(("Next ▶️", f"{prefix}:p:{page+1}"))
    rows = [row]
    if back_cd: rows.append(back(back_cd))
    return kb(rows)

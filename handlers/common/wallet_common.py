from utils.formatters import fmt_credits

def wallet_card(user):
    return (f"💰 <b>My Wallet</b>\n\n"
            f"💎 Credits: <b>{fmt_credits(user['credits_balance'])}</b>\n"
            f"💵 Value: ₹{fmt_credits(user['credits_balance'])}\n\n"
            f"📈 Total Purchased: {fmt_credits(user['credits_total_purchased'])}\n"
            f"📊 Total Spent: {fmt_credits(user['credits_total_spent'])}\n"
            f"🔄 Total Refunded: {fmt_credits(user['credits_total_refunded'])}")

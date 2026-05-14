from datetime import datetime, timezone
from decimal import Decimal

def fmt_credits(n):
    try:
        if n is None: return "0"
        if isinstance(n, int):
            return f"{n:,}"
        d = Decimal(str(n))
        if d == d.to_integral_value():
            return f"{int(d):,}"
        q = d.quantize(Decimal("0.01"))
        s = f"{q:,.2f}".rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(n)

def fmt_subs_short(n):
    try:
        n = int(n or 0)
    except Exception:
        return "0"
    if n < 1000:
        return str(n)
    if n < 1000000:
        v = n / 1000.0
        s = f"{v:.1f}".rstrip("0").rstrip(".")
        return f"{s}k"
    if n < 1000000000:
        v = n / 1000000.0
        s = f"{v:.1f}".rstrip("0").rstrip(".")
        return f"{s}M"
    v = n / 1000000000.0
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{s}B"

def fmt_time_remaining(end_dt):
    if not end_dt: return "-"
    now = datetime.now(timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    secs = int((end_dt - now).total_seconds())
    if secs <= 0: return "expired"
    h, rem = divmod(secs, 3600)
    m, _ = divmod(rem, 60)
    if h >= 24:
        d = h // 24; h = h % 24
        return f"{d}d {h}h"
    return f"{h}h {m}m"

def short(text, n=120):
    if not text: return ""
    return text if len(text) <= n else text[:n-1] + "…"

def activity_emoji(tier):
    return {"high":"🔥","medium":"⚡","low":"🌱","premium":"💎"}.get(tier or "low","⚡")

def status_emoji(status):
    return {
        "pending_approval":"⏳","approved":"✅","active":"🟢",
        "completed":"✔️","completed_early":"⚠️","cancelled":"❌","rejected":"🚫",
    }.get(status, "•")

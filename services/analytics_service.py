from database.queries.analytics import platform_overview, top_channels, bookings_last_7_days

async def get_overview():
    return await platform_overview()

async def get_top_channels(limit=10):
    return await top_channels(limit)

async def get_7day_chart():
    rows = await bookings_last_7_days()
    if not rows: return "No data yet."
    max_c = max(r["cnt"] for r in rows) or 1
    out = []
    for r in rows:
        bar = "▓" * int(r["cnt"] / max_c * 10) + "░" * (10 - int(r["cnt"] / max_c * 10))
        out.append(f"{r['day']} {bar} {r['cnt']}")
    return "\n".join(out)

# ChannelRent — Telegram Channel Ad Marketplace Bot

Production-grade marketplace bot where channel owners rent ad slots and advertisers pay with in-bot credits (₹1 = 1 credit). All money flows through the credits system for legal compliance.

## Features

- 🏪 Marketplace with category, activity, budget filters
- 💰 In-bot credits + UPI top-up flow
- 📢 Auto-post ads, auto-delete on expiry, pro-rata refunds
- 🛠️ Full superadmin panel — users, channels, bookings, financials, pricing, settings, analytics, broadcast
- 🔁 Atomic credit transactions (SELECT FOR UPDATE)
- 📅 APScheduler jobs for deletion, message-existence checks, reminders, low-credit alerts
- 🔒 Webhook validation, rate limiting, ban checks, role decorators

## Quick Start

### 1. Supabase
1. Create a project.
2. Get **DATABASE_URL** (Direct connection string).
3. Schema auto-applies on first start (`database/migrations/001_schema.sql`).

### 2. Bot
1. Talk to @BotFather → create bot → save **BOT_TOKEN**.
2. Set commands (BotFather → `/setcommands`):
   ```
   start - Open main menu
   admin - Admin panel
   help - How it works
   wallet - Credits wallet
   bookings - My bookings
   channels - My channels
   browse - Browse channels
   cancel - Cancel current action
   ```

### 3. Render
1. Push this repo to GitHub.
2. Render → New Web Service → connect repo → use `render.yaml`.
3. Set env vars: `BOT_TOKEN`, `SUPERADMIN_IDS`, `DATABASE_URL`, `WEBHOOK_URL` (your Render URL), `UPI_ID`, `UPI_NAME`, `SUPPORT_USERNAME`.
4. Deploy.

### 4. UptimeRobot
Add an HTTP monitor pointing to `https://your-app.onrender.com/health` every 5 minutes.

## Pricing Formula

```
S = subscribers, V = avg_views_24h, E = V/S × 100
view_score = min(V/max(S×0.8,1), 1) × 40
sub_score  = min(S/10000, 1) × 30
eng_score  = min(E/80, 1) × 30
score      = view + sub + eng (0..100)
tier: >=70 HIGH (×1.5), >=40 MEDIUM (×1.0), else LOW (×0.6)
price_per_hour = (base + S/1000 × price_per_1k + V/100 × price_per_100v) × multiplier
clamped to [MIN_LISTING_PRICE, MAX_LISTING_PRICE]
owner custom price clamped to ±50% of suggested.
```

## Refund Policy

- Advertiser ends booking early → pro-rata: owner keeps time-served earnings.
- Owner deletes (or message lost) → full refund to advertiser + reliability strike.
- Owner rejects booking → full refund instantly.
- Scheduled completion → no refund.

## Layout
See top-level folders. All code is in `channelrent_bot/`.

## Security Notes
- Never commit `.env`. Rotate any secret accidentally posted in chat.
- Webhook is protected with `WEBHOOK_SECRET` header.
- All credit ops use `SELECT FOR UPDATE` + transactions.

## Troubleshooting
- Bot not responding: check `/health` endpoint, ensure webhook URL is HTTPS, secret matches.
- Cannot post to channel: bot must be admin with post + delete permissions.
- "Already listed": that channel is registered under another owner.

Support: @Zluextic

# ChannelRent — Telegram Channel Ad Marketplace Bot

Production-grade Telegram bot that functions as a channel advertising marketplace:
- Channel Owners list channels for rent
- Advertisers pay with in-bot credits to post promotions
- Bot auto-broadcasts, tracks duration, auto-deletes, and handles pro-rata refunds
- Superadmin panel
- Credits system (INR 1 = 1 credit)

## Tech Stack
- Python 3.11+
- python-telegram-bot 21.3
- Supabase PostgreSQL via asyncpg
- APScheduler 3.10.4
- aiohttp 3.9.5

## Quick Deploy on Render
1. Fork/clone this repo
2. Create Supabase project, run `database/migrations/001_schema.sql`
3. Create Telegram bot via @BotFather
4. Connect repo to Render -> Web Service
5. Set env vars (see `.env.example`)
6. Set `WEBHOOK_URL` to Render URL
7. Deploy. Health endpoint at `/health`.

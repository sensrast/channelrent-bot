import asyncio
import logging
import os
import asyncpg
from pathlib import Path
import config

log = logging.getLogger(__name__)

class DB:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        if self.pool: return
        dsn = config.DATABASE_URL
        if "sslmode" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}sslmode=require"
        for attempt in range(5):
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=dsn, min_size=1, max_size=10,
                    command_timeout=30, max_inactive_connection_lifetime=300,
                )
                log.info("DB pool connected")
                return
            except Exception as e:
                log.warning("DB connect attempt %s failed: %s", attempt+1, e)
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Failed to connect to database")

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def migrate(self):
        path = Path(__file__).parent / "migrations" / "001_schema.sql"
        sql = path.read_text()
        async with self.pool.acquire() as conn:
            await conn.execute(sql)
        log.info("DB migrations applied")

    async def fetch(self, q, *a):
        async with self.pool.acquire() as c:
            return await c.fetch(q, *a)

    async def fetchrow(self, q, *a):
        async with self.pool.acquire() as c:
            return await c.fetchrow(q, *a)

    async def fetchval(self, q, *a):
        async with self.pool.acquire() as c:
            return await c.fetchval(q, *a)

    async def execute(self, q, *a):
        async with self.pool.acquire() as c:
            return await c.execute(q, *a)

    def acquire(self):
        return self.pool.acquire()

db = DB()

async def init_pool():
    await db.connect()
    await db.migrate()

async def close_pool():
    await db.close()

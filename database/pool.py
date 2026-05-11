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
        self._lock = asyncio.Lock()

    async def connect(self):
        if self.pool is not None:
            return
        async with self._lock:
            if self.pool is not None:
                return
            dsn = config.DATABASE_URL
            if not dsn:
                raise RuntimeError("DATABASE_URL not set")
            if "sslmode" not in dsn:
                sep = "&" if "?" in dsn else "?"
                dsn = f"{dsn}{sep}sslmode=require"
            last_err = None
            for attempt in range(5):
                try:
                    self.pool = await asyncpg.create_pool(
                        dsn=dsn, min_size=1, max_size=10,
                        command_timeout=30, max_inactive_connection_lifetime=300,
                    )
                    log.info("DB pool connected")
                    return
                except Exception as e:
                    last_err = e
                    log.warning("DB connect attempt %s failed: %s", attempt + 1, e)
                    await asyncio.sleep(2 ** attempt)
            raise RuntimeError(f"Failed to connect to database: {last_err}")

    async def _ensure(self):
        if self.pool is None:
            log.warning("DB pool was None at query time; reconnecting...")
            await self.connect()

    async def close(self):
        if self.pool:
            try:
                await self.pool.close()
            except Exception as e:
                log.warning("DB pool close failed: %s", e)
            self.pool = None

    async def migrate(self):
        await self._ensure()
        mig_dir = Path(__file__).parent / "migrations"
        files = sorted(mig_dir.glob("*.sql"))
        if not files:
            log.warning("No migration files found in %s", mig_dir)
            return
        async with self.pool.acquire() as conn:
            for f in files:
                try:
                    sql = f.read_text()
                    await conn.execute(sql)
                    log.info("Applied migration: %s", f.name)
                except Exception as e:
                    log.error("Migration %s failed: %s", f.name, e)
                    raise
        log.info("All DB migrations applied (%d files)", len(files))

    async def fetch(self, q, *a):
        await self._ensure()
        async with self.pool.acquire() as c:
            return await c.fetch(q, *a)

    async def fetchrow(self, q, *a):
        await self._ensure()
        async with self.pool.acquire() as c:
            return await c.fetchrow(q, *a)

    async def fetchval(self, q, *a):
        await self._ensure()
        async with self.pool.acquire() as c:
            return await c.fetchval(q, *a)

    async def execute(self, q, *a):
        await self._ensure()
        async with self.pool.acquire() as c:
            return await c.execute(q, *a)

    def acquire(self):
        if self.pool is None:
            raise RuntimeError("DB pool not initialized; call init_pool() first")
        return self.pool.acquire()

db = DB()

async def init_pool():
    await db.connect()
    await db.migrate()

async def close_pool():
    await db.close()

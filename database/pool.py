import asyncio
import logging
import os
import sys
import asyncpg
from pathlib import Path
import config

log = logging.getLogger(__name__)

def _p(msg):
    try:
        print(f"[pool] {msg}", flush=True)
    except Exception:
        pass

class DB:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()
        self._migrated = False

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
                    _p("DB pool connected")
                    log.info("DB pool connected")
                    return
                except Exception as e:
                    last_err = e
                    _p(f"DB connect attempt {attempt+1} failed: {e}")
                    log.warning("DB connect attempt %s failed: %s", attempt + 1, e)
                    await asyncio.sleep(2 ** attempt)
            raise RuntimeError(f"Failed to connect to database: {last_err}")

    async def _ensure(self):
        if self.pool is None:
            _p("DB pool was None at query time; reconnecting...")
            log.warning("DB pool was None at query time; reconnecting...")
            await self.connect()
        if not self._migrated:
            try:
                await self.migrate()
            except Exception as e:
                _p(f"migrate (lazy) failed: {e}")
                log.error("migrate (lazy) failed: %s", e)

    async def close(self):
        if self.pool:
            try:
                await self.pool.close()
            except Exception as e:
                log.warning("DB pool close failed: %s", e)
            self.pool = None
            self._migrated = False

    async def migrate(self):
        if self.pool is None:
            await self.connect()
        mig_dir = Path(__file__).parent / "migrations"
        files = sorted(mig_dir.glob("*.sql"))
        _p(f"Running {len(files)} migration files")
        async with self.pool.acquire() as conn:
            for f in files:
                sql = f.read_text()
                ok = 0; failed = 0
                for stmt in _split_sql(sql):
                    try:
                        await conn.execute(stmt)
                        ok += 1
                    except Exception as e:
                        failed += 1
                        _p(f"Migration {f.name} stmt failed (continuing): {e} | stmt={stmt[:120]}")
                        log.warning("Migration %s stmt failed (continuing): %s | stmt=%s", f.name, e, stmt[:150])
                _p(f"Migration {f.name} applied: {ok} ok, {failed} failed")
                log.info("Migration %s applied: %d ok, %d failed", f.name, ok, failed)
            defensive = [
                "ALTER TABLE channels ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
                "UPDATE channels SET is_active=TRUE WHERE is_active IS NULL",
                "ALTER TABLE channel_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
                "UPDATE channel_categories SET is_active=TRUE WHERE is_active IS NULL",
            ]
            for stmt in defensive:
                try:
                    await conn.execute(stmt)
                    _p(f"Defensive applied: {stmt[:80]}")
                    log.info("Defensive applied: %s", stmt[:80])
                except Exception as e:
                    _p(f"Defensive failed: {stmt[:80]} | {e}")
                    log.error("Defensive failed: %s | %s", stmt[:80], e)
        self._migrated = True
        _p("DB migrations complete")
        log.info("DB migrations complete")

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


def _split_sql(sql: str):
    import re as _re
    out, buf, i, n = [], [], 0, len(sql)
    in_sq = False
    in_dollar = False
    dollar_tag = ""
    while i < n:
        ch = sql[i]
        if not in_sq and not in_dollar and ch == "-" and i + 1 < n and sql[i+1] == "-":
            while i < n and sql[i] != "\n":
                buf.append(sql[i]); i += 1
            continue
        if not in_dollar and ch == "'":
            in_sq = not in_sq
            buf.append(ch); i += 1; continue
        if not in_sq and ch == "$":
            m = _re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                if not in_dollar:
                    in_dollar = True; dollar_tag = tag
                elif tag == dollar_tag:
                    in_dollar = False; dollar_tag = ""
                buf.append(tag); i += len(tag); continue
        if ch == ";" and not in_sq and not in_dollar:
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1; continue
        buf.append(ch); i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


db = DB()

async def init_pool():
    _p("init_pool: connecting...")
    await db.connect()
    _p("init_pool: migrating...")
    await db.migrate()
    _p("init_pool: done")

async def close_pool():
    await db.close()

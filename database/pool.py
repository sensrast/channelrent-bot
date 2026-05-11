"""Asyncpg pool management."""
import asyncpg
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
_pool = None


async def init_pool(dsn):
    global _pool
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10, command_timeout=30)
    logger.info('DB pool ready')


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool():
    if _pool is None:
        raise RuntimeError('Pool not initialized')
    return _pool


async def run_migrations():
    pool = get_pool()
    sql_file = Path(__file__).parent / 'migrations' / '001_schema.sql'
    if not sql_file.exists():
        logger.warning('Migration file missing')
        return
    sql = sql_file.read_text()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info('Migrations applied')


async def fetch(query, *args):
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query, *args):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query, *args):
    async with get_pool().acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query, *args):
    async with get_pool().acquire() as conn:
        return await conn.execute(query, *args)

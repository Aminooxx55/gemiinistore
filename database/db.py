import aiosqlite
from contextlib import asynccontextmanager
from config import DB_PATH


@asynccontextmanager
async def get_db():
    """Async context manager — use as: async with get_db() as db:"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db

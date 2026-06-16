"""Async SQLAlchemy engine/session (SQLite, WAL).

Used by the admin role for groups/servers and by the node role for instance
persistence. Schema lives in models.py; created on startup during migration.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import get_settings


class Base(DeclarativeBase):
    pass


def _db_url() -> str:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{settings.data_dir / 'data.db'}"


engine = create_async_engine(_db_url(), echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite WAL for better concurrent reads, as in the originals.
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")

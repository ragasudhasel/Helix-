"""
Async SQLAlchemy engine and session factory for SQLite.
Uses aiosqlite driver — no blocking I/O on the event loop.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    # SQLite needs this for async to work correctly
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_all() -> None:
    """Create all tables on startup. No migrations required per spec."""
    from app.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Dependency that yields an async session, auto-closing on exit."""
    async with async_session_factory() as session:
        yield session

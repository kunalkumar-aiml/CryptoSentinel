"""
Async SQLAlchemy session + table auto-creation.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from database.models import Base
from config import settings
from utils.logger import get_logger

log = get_logger("database")

# Async engine (for FastAPI)
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine (for Alembic)
sync_engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)


async def create_tables():
    """Create all tables on startup if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database.tables_ready")


async def get_db():
    """FastAPI dependency — yields async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

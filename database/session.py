from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from database.models import Base
from config import settings
from utils.logger import get_logger

log = get_logger("database")

async_connect_args = {}
if "localhost" not in settings.DATABASE_URL and "127.0.0.1" not in settings.DATABASE_URL:
    async_connect_args["ssl"] = "require"

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_connect_args = {}
if "localhost" not in settings.DATABASE_URL_SYNC and "127.0.0.1" not in settings.DATABASE_URL_SYNC:
    sync_connect_args["sslmode"] = "require"

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=False,
    connect_args=sync_connect_args,
)

async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database.tables_ready")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

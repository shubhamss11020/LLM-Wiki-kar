import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.app.config import settings
from backend.app.database.models import Base

logger = logging.getLogger(__name__)

# Determine database engine
try:
    engine = create_async_engine(settings.async_database_url, echo=False, future=True)
except Exception as e:
    logger.warning(f"Could not initialize PostgreSQL engine ({e}), falling back to SQLite.")
    engine = create_async_engine(settings.SQLITE_FALLBACK_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

from sqlalchemy import text

async def init_db():
    """Initializes the database schema with automatic SQLite fallback."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE files ADD COLUMN partition INTEGER DEFAULT 1;"))
            except Exception:
                pass
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.warning(f"Could not connect to database ({e}), attempting fallback to SQLite.")
        engine = create_async_engine(settings.SQLITE_FALLBACK_URL, echo=False, future=True)
        AsyncSessionLocal.configure(bind=engine)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE files ADD COLUMN partition INTEGER DEFAULT 1;"))
            except Exception:
                pass
        logger.info("SQLite fallback tables initialized successfully.")

async def get_db():
    """FastAPI Dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


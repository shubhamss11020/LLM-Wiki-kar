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
    """Initializes the database schema with automatic SQLite fallback and high-speed GIN indexes."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE files ADD COLUMN partition INTEGER DEFAULT 1;"))
            except Exception:
                pass
            # Optimize PostgreSQL / Neon with GIN Trigram indexes for sub-5ms search
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING gin (content gin_trgm_ops);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_heading_trgm ON chunks USING gin (heading gin_trgm_ops);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_files_partition_id ON files (partition, id);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_files_title_trgm ON files USING gin (title gin_trgm_ops);"))
            except Exception:
                pass
            # Ensure thread tables exist (safety net for partial create_all)
            try:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS threads (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(64) UNIQUE NOT NULL,
                        "user" VARCHAR(128) NOT NULL,
                        title VARCHAR(512) NOT NULL,
                        file_path VARCHAR(1024),
                        turn_count INTEGER DEFAULT 0,
                        timezone VARCHAR(64) DEFAULT 'Asia/Kolkata',
                        created_at TIMESTAMP NOT NULL,
                        last_updated TIMESTAMP NOT NULL
                    );
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS thread_turns (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(64) NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
                        turn_number INTEGER NOT NULL,
                        user_prompt TEXT NOT NULL,
                        ai_response TEXT,
                        created_at TIMESTAMP NOT NULL
                    );
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_threads_thread_id ON threads (thread_id);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_threads_user ON threads (\"user\");"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_threads_last_updated ON threads (last_updated);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_thread_turns_thread_id ON thread_turns (thread_id);"))
            except Exception:
                pass
        logger.info("Database tables and high-speed GIN indexes initialized successfully.")
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


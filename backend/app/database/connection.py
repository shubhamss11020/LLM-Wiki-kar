import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from backend.app.config import settings
from backend.app.database.models import Base

logger = logging.getLogger(__name__)

# Determine if SSL is required (Neon DB, AWS, Render, or explicit sslmode)
connect_args = {}
raw_url = settings.DATABASE_URL.lower()
if any(k in raw_url for k in ["neon.tech", "sslmode=require", "render.com", "aws", "pooler"]):
    connect_args["ssl"] = "require"

engine = create_async_engine(
    settings.async_database_url,
    connect_args=connect_args,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db():
    """
    Initializes PostgreSQL database schema with high-speed GIN trigram indexes
    and thread monitoring tables.
    """
    global engine, AsyncSessionLocal
    try:
        # Step 1: Base table creation
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Step 2: Ensure partition column
        try:
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE files ADD COLUMN IF NOT EXISTS partition INTEGER DEFAULT 1;"))
        except Exception:
            pass

        # Step 3: GIN Trigram indexes
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING gin (content gin_trgm_ops);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_heading_trgm ON chunks USING gin (heading gin_trgm_ops);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_files_partition_id ON files (partition, id);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_files_title_trgm ON files USING gin (title gin_trgm_ops);"))
        except Exception as e:
            logger.info(f"PostgreSQL pg_trgm extension note: {e}")

        # Step 4: Ensure thread tables and indexes exist
        try:
            async with engine.begin() as conn:
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

                # Idempotency & Audit Trails
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS idempotency_keys (
                        key VARCHAR(64) PRIMARY KEY,
                        thread_id VARCHAR(64) NOT NULL,
                        turn_number INTEGER NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
                        response_payload JSON,
                        created_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP
                    );
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS thread_audit_logs (
                        id SERIAL PRIMARY KEY,
                        event_id VARCHAR(64) UNIQUE NOT NULL,
                        thread_id VARCHAR(64) NOT NULL,
                        turn_number INTEGER NOT NULL DEFAULT 1,
                        event_type VARCHAR(64) NOT NULL,
                        user_identity VARCHAR(128) NOT NULL DEFAULT 'shubh',
                        idempotency_key VARCHAR(64),
                        execution_time_ms INTEGER DEFAULT 0,
                        payload_preview JSON,
                        created_at TIMESTAMP NOT NULL
                    );
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_idempotency_thread ON idempotency_keys (thread_id, turn_number);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_thread_id ON thread_audit_logs (thread_id);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON thread_audit_logs (event_type);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON thread_audit_logs (created_at);"))
        except Exception as e:
            logger.warning(f"Thread table DDL: {e}")


        # Step 5: Auto-migrate any unmigrated generations into threads
        try:
            async with engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO threads (thread_id, "user", title, file_path, turn_count, timezone, created_at, last_updated)
                    SELECT 
                        'thr-' || SUBSTRING(MD5(record_id), 1, 8),
                        'shubh',
                        COALESCE(SUBSTRING(prompt FROM 1 FOR 60), 'Conversation'),
                        file_path,
                        1,
                        COALESCE(timezone, 'Asia/Kolkata'),
                        created_at,
                        created_at
                    FROM generations g
                    WHERE g.record_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM threads t WHERE t.thread_id = ('thr-' || SUBSTRING(MD5(g.record_id), 1, 8))
                      );
                """))
                await conn.execute(text("""
                    INSERT INTO thread_turns (thread_id, turn_number, user_prompt, ai_response, created_at)
                    SELECT 
                        'thr-' || SUBSTRING(MD5(record_id), 1, 8),
                        1,
                        prompt,
                        response,
                        created_at
                    FROM generations g
                    WHERE g.record_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM thread_turns tt 
                          WHERE tt.thread_id = ('thr-' || SUBSTRING(MD5(g.record_id), 1, 8)) 
                            AND tt.turn_number = 1
                      );
                """))
        except Exception as e:
            logger.info(f"Generation migration note: {e}")

        logger.info("PostgreSQL database tables and GIN indexes initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL database schema: {e}", exc_info=True)
        raise

async def get_db():
    """FastAPI Dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

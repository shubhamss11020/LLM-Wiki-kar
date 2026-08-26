import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Knowledge Base Wiki"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://wiki_user:wiki_password@localhost:5432/llm_wiki"
    )
    # Fallback to local SQLite if PostgreSQL is unavailable during local development
    SQLITE_FALLBACK_URL: str = "sqlite+aiosqlite:///./llm_wiki.db"
    
    # Path to the Obsidian Vault
    VAULT_PATH: str = os.getenv(
        "VAULT_PATH", 
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vault"))
    )
    
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    class Config:
        env_file = ".env"

settings = Settings()

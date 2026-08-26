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
    
    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Strip sslmode=require if present for asyncpg compatibility
        if "?sslmode=" in url:
            url = url.split("?sslmode=")[0]
        elif "&sslmode=" in url:
            url = url.split("&sslmode=")[0]
        return url

    class Config:
        env_file = ".env"

settings = Settings()

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Knowledge Base Wiki"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://wiki_user:wiki_password@localhost:5432/llm_wiki"
    )
    
    # Path to the Obsidian Vault
    VAULT_PATH: str = os.getenv(
        "VAULT_PATH", 
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vault"))
    )
    
    # Public server URL (used as OAuth issuer)
    SERVER_URL: str = os.getenv(
        "SERVER_URL",
        "https://llm-wiki-kar.onrender.com"
    )
    DEFAULT_TIMEZONE: str = "America/New_York"
    
    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Asyncpg uses query params or connect_args for SSL. Strip query params if needed
        if "?" in url:
            base_url = url.split("?")[0]
            return base_url
        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

settings = Settings()

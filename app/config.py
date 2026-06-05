from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    OPENAI_API_KEY: str
    # PostgreSQL connection string
    # Format: postgresql+psycopg2://user:password@host:5432/dbname
    # For Neon: postgresql+psycopg2://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
    DATABASE_URL: str
    SCHEDULER_INTERVAL_MINUTES: int = 2
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_TIMEOUT: int = 30
    MOCK_DATA_PATH: str = "mock_data/emails.json"

    # Email source: "mock" reads local JSON, "gmail" uses IMAP
    EMAIL_SOURCE: str = "mock"

    # Gmail IMAP settings (required when EMAIL_SOURCE=gmail)
    GMAIL_USER: Optional[str] = None
    GMAIL_APP_PASSWORD: Optional[str] = None
    GMAIL_MAX_EMAILS: int = 20
    GMAIL_FOLDER: str = "INBOX"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

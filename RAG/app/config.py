"""
SROP Configuration — loaded from environment variables via pydantic-settings.
Never hardcode secrets.
"""

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings sourced from .env or environment."""

    GEMINI_API_KEY: str = ""
    CHROMA_PATH: str = "./chroma_db"
    DATABASE_URL: str = "sqlite+aiosqlite:///./srop.db"
    LLM_TIMEOUT_SECONDS: int = 30
    GEMINI_MODEL: str = "gemini-2.0-flash"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()

if settings.GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY

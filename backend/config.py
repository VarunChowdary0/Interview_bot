from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # LLM Configuration
    llm_provider: Literal["openai", "claude"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # LLM Parameters
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_timeout: int = 30

    # Interview Settings
    default_max_questions: int = 10
    default_max_followups: int = 2
    session_timeout_minutes: int = 60

    # Database (existing)
    database_url: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

"""Application settings loaded from environment."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the document AI service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",  # use exact env names below via Field(alias=...)
    )

    # OpenAI (env: OPENAI_API_KEY, MODEL_TO_USE, TEMPERATURE, MAX_TOKENS)
    openai_api_key: str = ""
    model_to_use: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096

    # Server (env: PORT, HOST)
    port: int = 8000
    host: str = "0.0.0.0"

    # Resilience (env: RETRY)
    retry: int = 3

    # Logging (env: LOG_LEVEL)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

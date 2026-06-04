"""Environment-backed settings for the API service."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DEVFLOW_API_",
        extra="ignore",
    )

    project_name: str = "DevFlow Insight API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://devflow:devflow@localhost:5432/devflow"
    cors_origins: list[AnyUrl] = Field(default_factory=list)
    secret_key: str = "changeme-dev-only-use-random-32-chars-in-prod"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()

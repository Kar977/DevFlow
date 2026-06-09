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

    # GitHub OAuth App
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = (
        "http://localhost:8000/api/v1/integrations/github/callback"
    )

    # Fernet key for encrypting GitHub access tokens at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # noqa: E501
    github_token_encryption_key: str = ""

    # Shared secret used to verify GitHub webhook HMAC-SHA256 signatures
    github_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()

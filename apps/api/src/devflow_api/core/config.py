"""Environment-backed settings for the API service."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "changeme-dev-only-use-random-32-chars-in-prod"
_MIN_SECRET_KEY_LEN = 32
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


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
    secret_key: str = _DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Allowed hosts for TrustedHostMiddleware (empty = no enforcement)
    allowed_hosts: list[str] = Field(default_factory=list)

    # GitHub OAuth App
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:3000/integrations/github/callback"

    # OAuth scope — minimal by default. Set to "read:user,repo" when
    # private-repository issue sync is required.
    # Example: DEVFLOW_API_GITHUB_OAUTH_SCOPES="read:user,repo"
    github_oauth_scopes: str = "read:user"

    # Fernet key for encrypting GitHub access tokens at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # noqa: E501
    github_token_encryption_key: str = ""

    # Shared secret used to verify GitHub webhook HMAC-SHA256 signatures
    github_webhook_secret: str = ""

    # GitHub App (repository access via installations). The private key is a
    # PEM string; single-line env values may escape newlines as "\n".
    github_app_id: str = ""
    github_app_slug: str = ""
    github_app_private_key: str = ""

    @property
    def github_app_private_key_pem(self) -> str:
        """Return the private key with escaped newlines normalized."""
        return self.github_app_private_key.replace("\\n", "\n")

    # Redis cache for metrics endpoints (empty = use in-memory cache)
    redis_url: str = ""
    metrics_cache_ttl_seconds: int = 60

    # Work sessions running longer than this are flagged as likely-forgotten
    # in GET /tasks/sessions/active — a warning only, nothing is stopped
    # automatically.
    long_running_session_hours: int = 6

    # Read-only showcase deployment: DemoReadOnlyMiddleware blocks every
    # mutating request (see main.py) and entrypoint.sh reseeds the database
    # on every container start (see devflow_api.demo). Never enable this
    # against a database holding real data — the seeder truncates it.
    demo_mode: bool = False

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Settings:
        """Refuse to start in production with unsafe / default configuration."""
        if self.environment != "production":
            return self

        errors: list[str] = []

        if self.debug:
            errors.append("debug must be False in production")

        if (
            self.secret_key == _DEFAULT_SECRET_KEY
            or len(self.secret_key) < _MIN_SECRET_KEY_LEN
        ):
            errors.append(
                f"secret_key must be at least {_MIN_SECRET_KEY_LEN} characters "
                "and must not be the default value"
            )

        # GitHub integration secrets — required when OAuth is enabled
        if self.github_client_id:
            if not self.github_client_secret:
                errors.append(
                    "github_client_secret is required when github_client_id is set"
                )
            if not self.github_token_encryption_key:
                errors.append(
                    "github_token_encryption_key is required "
                    "when github_client_id is set"
                )

        # GitHub App secrets — required when the App integration is enabled
        if self.github_app_id:
            for field_name in (
                "github_app_slug",
                "github_app_private_key",
                "github_webhook_secret",
            ):
                if not getattr(self, field_name):
                    errors.append(f"{field_name} is required when github_app_id is set")

        # Localhost in CORS origins signals a local-only configuration
        for origin in self.cors_origins:
            host = str(origin)
            if any(local in host for local in _LOCAL_HOSTS):
                errors.append(
                    f"cors_origins must not contain local addresses in production "
                    f"(found: {host})"
                )

        # TrustedHostMiddleware should be configured in production
        if not self.allowed_hosts:
            errors.append(
                "allowed_hosts must be set in production to prevent host-header attacks"
            )
        else:
            for h in self.allowed_hosts:
                if h in ("*", ""):
                    errors.append(
                        "allowed_hosts must not contain wildcard '*' in production"
                    )

        if errors:
            bullet_list = "\n  - ".join(errors)
            raise ValueError(
                f"Unsafe configuration for environment='production':\n  - {bullet_list}"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()

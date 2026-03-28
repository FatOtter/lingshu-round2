"""Application configuration via environment variables."""

import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_UNSAFE_JWT_SECRETS = frozenset({
    "change-me-in-production",
    "change-me",
    "secret",
    "dev-secret",
    "dev-secret-round2",
})


class Settings(BaseSettings):
    """LingShu application settings loaded from environment variables."""

    model_config = {"env_prefix": "LINGSHU_"}

    # Server
    server_port: int = 8000
    server_env: str = "development"  # development / staging / production
    cors_origins: str = "http://localhost:3000,http://localhost:3100"  # comma-separated

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://lingshu:lingshu@localhost:5432/lingshu"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Nessie (branch management) — optional, None disables branch features
    nessie_url: str | None = None

    # Auth — defaults to "production"; dev mode requires explicit opt-in
    auth_mode: str = "production"  # dev / production
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl: int = 900  # 15 minutes
    refresh_token_ttl: int = 604800  # 7 days

    # OIDC / SSO — all optional; SSO is disabled when issuer_url is empty
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    oidc_provider_name: str = "SSO"

    # Gemini (legacy, use copilot_* settings instead)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Copilot LLM provider
    copilot_provider: str = "gemini"  # gemini / openai / anthropic
    copilot_api_key: str = ""
    copilot_model: str = ""

    # EditLog backend: "postgres" (default) or "fdb"
    editlog_backend: str = "postgres"
    fdb_cluster_file: str = "/etc/foundationdb/fdb.cluster"

    # RBAC — enabled by default; disable only for local development
    rbac_enabled: bool = True

    # Seed
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "change_me_123"
    seed_tenant_name: str = "Default"

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Reject known-unsafe JWT secrets in production."""
        if self.server_env == "production":
            if self.jwt_secret.lower() in _UNSAFE_JWT_SECRETS:
                raise ValueError(
                    "LINGSHU_JWT_SECRET must be set to a strong, unique value "
                    "in production. Current value is a known placeholder."
                )
        elif self.jwt_secret.lower() in _UNSAFE_JWT_SECRETS:
            logger.warning(
                "Using placeholder JWT secret — acceptable for development only"
            )
        return self

    @property
    def is_dev(self) -> bool:
        return self.auth_mode == "dev"

    @property
    def is_production(self) -> bool:
        return self.server_env == "production"

    @property
    def sso_enabled(self) -> bool:
        return bool(self.oidc_issuer_url and self.oidc_client_id)


def get_settings() -> Settings:
    """Create settings instance (cached at module level)."""
    return Settings()

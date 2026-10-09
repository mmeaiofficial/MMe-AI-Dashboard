"""Settings from environment variables. Production refuses to start with unsafe values."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

UNSAFE_SECRETS = {"", "change-me", "changeme", "secret", "your-secret-key-change-in-production", "dev-secret"}


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    env: str = "development"                    # development | staging | production
    secret_key: str = "dev-secret"
    database_url: str = "postgresql+psycopg://mme:mme@localhost:5432/mme_os"
    redis_url: str = "redis://localhost:6379/0"
    web_origin: str = "http://localhost:3000"
    api_origin: str = "http://localhost:8000"
    google_client_id: str = ""
    google_client_secret: str = ""
    field_encryption_keys: str = ""             # "kid:base64,kid2:base64"
    field_encryption_active_kid: str = ""
    session_hours: int = 12
    session_idle_minutes: int = 120
    s3_endpoint: str = ""
    s3_bucket: str = "mme-os"
    bootstrap_super_admins: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.env != "development"

    def validate(self) -> None:
        problems = []
        if self.env not in ("development", "staging", "production"):
            problems.append("APP_ENV must be development, staging or production")
        if self.env != "development":
            if self.secret_key in UNSAFE_SECRETS or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be a random value of at least 32 characters")
            if not self.field_encryption_keys or not self.field_encryption_active_kid:
                problems.append("FIELD_ENCRYPTION_KEYS and FIELD_ENCRYPTION_ACTIVE_KID are required")
            if not self.google_client_id or not self.google_client_secret:
                problems.append("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required")
            if not self.web_origin.startswith("https://") or not self.api_origin.startswith("https://"):
                problems.append("WEB_ORIGIN and API_ORIGIN must use https")
            if "mme:mme@" in self.database_url:
                problems.append("DATABASE_URL still uses the development credentials")
        if problems:
            raise ConfigError("Refusing to start: " + "; ".join(problems))


def _sqlalchemy_url(url: str) -> str:
    """Hosted Postgres (Neon, Supabase, Vercel) gives postgres:// or postgresql://; we drive it with psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    s = Settings(
        env=env.get("APP_ENV", "development"),
        secret_key=env.get("SECRET_KEY", "dev-secret"),
        database_url=_sqlalchemy_url(env.get("DATABASE_URL", Settings.database_url)),
        redis_url=env.get("REDIS_URL") or env.get("KV_URL") or Settings.redis_url,
        web_origin=env.get("WEB_ORIGIN", Settings.web_origin),
        api_origin=env.get("API_ORIGIN", Settings.api_origin),
        google_client_id=env.get("GOOGLE_CLIENT_ID", ""),
        google_client_secret=env.get("GOOGLE_CLIENT_SECRET", ""),
        field_encryption_keys=env.get("FIELD_ENCRYPTION_KEYS", ""),
        field_encryption_active_kid=env.get("FIELD_ENCRYPTION_ACTIVE_KID", ""),
        session_hours=int(env.get("SESSION_HOURS", "12")),
        session_idle_minutes=int(env.get("SESSION_IDLE_MINUTES", "120")),
        s3_endpoint=env.get("S3_ENDPOINT", ""),
        s3_bucket=env.get("S3_BUCKET", "mme-os"),
        bootstrap_super_admins=tuple(e.strip().lower() for e in env.get("BOOTSTRAP_SUPER_ADMINS", "").split(",") if e.strip()),
    )
    s.validate()
    return s

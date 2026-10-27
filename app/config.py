import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("app")


class Settings(BaseSettings):
    """Read from environment variables or a .env file (see .env.example)."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/charter"
    # "development" or "production". Production hides /docs and sends HSTS; it also refuses to start without SECRET_KEY.
    environment: str = "development"

    # signs the login tokens. Generate one with:  python -c "import secrets; print(secrets.token_urlsafe(48))"
    secret_key: str = ""
    access_token_minutes: int = 60

    # comma separated; the frontend dev servers (React/Vite/Next/Angular) by default
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:4200"
    # Host headers the API answers to (blocks host-header attacks); add your domain in production
    allowed_hosts: str = "localhost,127.0.0.1,testserver"

    # a flight can be booked no sooner than this many minutes from now ...
    min_lead_minutes: int = 30
    # ... and no later than this many days ahead
    max_advance_days: int = 365

    # abuse protection (per client IP, per minute)
    rate_limit_per_minute: int = 300
    auth_rate_limit_per_minute: int = 10
    # lock an account for lockout_minutes after this many wrong passwords in a row
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    max_body_bytes: int = 64 * 1024

    @property
    def production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


settings = Settings()

if len(settings.secret_key) < 32:
    if settings.production:
        raise RuntimeError("SECRET_KEY must be set (32+ characters) when ENVIRONMENT=production")
    # fine for a quick try-out, but every restart logs everyone out
    settings.secret_key = secrets.token_urlsafe(48)
    log.warning("SECRET_KEY is not set in .env: using a temporary one, logins will not survive a restart")

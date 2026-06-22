"""
Application configuration.
All settings are read from environment variables (or .env file).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_port: int = 8000
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    timezone: str = "Asia/Kolkata"

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str
    database_url_async: str = ""
    database_url_test: str = ""

    # Pool settings
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800  # 30 minutes

    # ── Security ──────────────────────────────────────────────────────────
    vapi_secret: str = ""
    api_secret_key: str = "change-me-in-production"

    # ── Vapi ──────────────────────────────────────────────────────────────
    vapi_api_key: str = ""
    vapi_phone_number_id: str = ""
    vapi_assistant_id: str = ""

    # ── OpenAI ───────────────────────────────────────────────────────────
    openai_api_key: str = ""

    # ── Slot Generation ───────────────────────────────────────────────────
    slot_generation_days: int = 14
    slot_duration_minutes: int = 15

    # ── CORS ──────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"

    @property
    def effective_database_url(self) -> str:
        """Return the test DB URL when running in testing mode."""
        if self.is_testing and self.database_url_test:
            return self.database_url_test
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()

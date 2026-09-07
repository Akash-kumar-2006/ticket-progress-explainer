"""Application configuration loaded from environment / .env file."""
from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = f"sqlite:///{(PROJECT_ROOT / 'ticket_progress.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = DEFAULT_DB
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rules_version: str = "1.0.0"
    model_version: str = "1.0.0"
    reference_date: str = "2026-09-07"

    # Optional / opt-in LLM provider. Leave empty to use the rule-based engine.
    llm_provider: str = ""
    llm_api_key: str = ""

    ticketing_integration: str = "stub"

    @property
    def reference_date_obj(self) -> date:
        try:
            return date.fromisoformat(self.reference_date)
        except ValueError:
            return date(2026, 9, 7)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
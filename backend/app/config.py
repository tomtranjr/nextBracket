"""App settings. Read from environment variables that start with `NEXTBRACKET_`."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEXTBRACKET_")

    # Default is resolved from this file, so it works from any working directory.
    standards_dir: Path = Path(__file__).parents[1] / "data" / "standards"

    # Browser origins allowed to call the API. Set as a JSON list, for example
    # NEXTBRACKET_CORS_ORIGINS='["https://example.app"]'. The default is the local dev site.
    # The deploy PR sets the real site here.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Requests per minute. They cap cost on the public API: one client address, and all
    # clients together. 0 turns a limit off. The counters live in memory, so they are exact only
    # while Cloud Run runs a single instance.
    # ge=0: a negative value would block every request, so it fails at startup instead.
    rate_limit_per_ip: int = Field(default=60, ge=0)
    rate_limit_global: int = Field(default=600, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

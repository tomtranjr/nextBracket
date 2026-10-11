"""App settings. Read from environment variables that start with `NEXTBRACKET_`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEXTBRACKET_")

    # Default is resolved from this file, so it works from any working directory.
    standards_dir: Path = Path(__file__).parents[1] / "data" / "standards"


@lru_cache
def get_settings() -> Settings:
    return Settings()

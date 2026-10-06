from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration loaded from CELLSCOPE_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CELLSCOPE_", env_file=ROOT / ".env", extra="ignore"
    )

    app_name: str = "CellScope AI"
    version: str = "0.1.0"
    max_upload_mb: int = 15
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    log_level: str = "INFO"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


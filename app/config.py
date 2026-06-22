"""Application settings (Pydantic Settings) and cached preset loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import Debater

BASE_DIR = Path(__file__).resolve().parent
PRESETS_PATH = BASE_DIR / "presets.yaml"


class Settings(BaseSettings):
    """Application settings, loaded from a ``.env`` file at the project root.

    Mirrors the keys consumers relied on via the previous hand-rolled
    ``Settings`` class (``settings.api_base_url`` etc.) but with Pydantic
    validation and defaults baked into the field metadata.
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-reasoner"
    brave_api_key: str = ""


@lru_cache(maxsize=1)
def load_presets() -> list[Debater]:
    """Load preset debaters from YAML, cached after the first call.

    ``presets.yaml`` is static, so the parsed result is memoised to avoid
    re-reading and re-parsing the file on every request.
    """
    with open(PRESETS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return [Debater(**d) for d in data.get("debaters", [])]


# Global settings instance
settings = Settings()

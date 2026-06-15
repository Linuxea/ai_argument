from pathlib import Path

import yaml
from dotenv import dotenv_values

from models import Debater

PRESETS_PATH = Path(__file__).parent / "presets.yaml"

# Load .env file — returns a dict without touching os.environ
_env = dotenv_values(Path(__file__).parent / ".env")


def load_presets() -> list[Debater]:
    """Load preset debaters from YAML file."""
    with open(PRESETS_PATH) as f:
        data = yaml.safe_load(f)
    return [Debater(**d) for d in data["debaters"]]


class Settings:
    """Application settings loaded exclusively from .env file."""

    def __init__(self):
        self.api_base_url = _env.get("API_BASE_URL", "https://api.deepseek.com")
        self.api_key = _env.get("API_KEY", "")
        self.model = _env.get("MODEL", "deepseek-reasoner")
        self.brave_api_key = _env.get("BRAVE_API_KEY", "")


# Global settings instance
settings = Settings()

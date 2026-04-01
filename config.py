import yaml
from pathlib import Path
from models import Debater


PRESETS_PATH = Path(__file__).parent / "presets.yaml"


def load_presets() -> list[Debater]:
    """Load preset debaters from YAML file."""
    with open(PRESETS_PATH) as f:
        data = yaml.safe_load(f)
    return [Debater(**d) for d in data["debaters"]]


class Settings:
    """Application settings with defaults for Ollama."""

    def __init__(
        self,
        api_base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "llama3",
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.model = model


# Global settings instance
settings = Settings()

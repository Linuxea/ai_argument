import os
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
    """Application settings with defaults for DeepSeek."""

    def __init__(
        self,
        api_base_url: str = "https://api.deepseek.com",
        api_key: str = None,
        model: str = "deepseek-reasoner",
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model
        self.brave_api_key = os.environ.get("BRAVE_API_KEY", "")


def build_model_string(base_url: str, model: str) -> str:
    """Convert API settings to a PydanticAI model string."""
    KNOWN_PROVIDERS = {
        "api.deepseek.com": "deepseek",
        "api.openai.com": "openai",
    }
    for host, provider in KNOWN_PROVIDERS.items():
        if host in base_url:
            return f"{provider}:{model}"
    return f"openai:{model}"


# Global settings instance
settings = Settings()

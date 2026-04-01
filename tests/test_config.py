import os
from config import load_presets, Settings


def test_load_presets_returns_list_of_debaters():
    presets = load_presets()
    assert len(presets) == 3
    assert presets[0].name == "The Skeptic"
    assert presets[1].name == "The Optimist"
    assert presets[2].name == "The Analyst"


def test_settings_defaults():
    settings = Settings()
    assert settings.api_base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-chat"
    assert settings.api_key == os.environ.get("DEEPSEEK_API_KEY", "")

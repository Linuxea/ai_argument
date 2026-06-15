from dotenv import dotenv_values

from app.config import load_presets, Settings

# Read the actual .env values once so the settings tests are stable regardless
# of whether a developer has configured real API keys locally.
_env = dotenv_values(".env")


def test_load_presets_returns_list_of_debaters():
    presets = load_presets()
    assert len(presets) == 3
    # Preset names are in Chinese (see presets.yaml)
    assert presets[0].name == "正方"
    assert presets[1].name == "反方"
    assert presets[2].name == "分析家"


def test_settings_defaults():
    settings = Settings()
    # Pydantic Settings reads the .env file; assert against the same source so
    # the test is stable in any developer environment.
    assert settings.api_base_url == _env.get("API_BASE_URL", "https://api.deepseek.com")
    assert settings.model == _env.get("MODEL", "deepseek-reasoner")
    assert settings.api_key == _env.get("API_KEY", "")
    assert settings.brave_api_key == _env.get("BRAVE_API_KEY", "")


def test_load_presets_is_cached(monkeypatch):
    """The preset list is memoised: the YAML file is read at most once."""
    load_presets.cache_clear()

    original_open = open
    call_count = {"n": 0}

    def counting_open(path, *args, **kwargs):
        if str(path).endswith("presets.yaml"):
            call_count["n"] += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)

    load_presets()
    load_presets()
    load_presets()

    assert call_count["n"] == 1, "presets.yaml should be read only once thanks to caching"

    # Restore unpatched state for any later tests
    load_presets.cache_clear()

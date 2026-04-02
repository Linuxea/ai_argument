import os
from config import load_presets, Settings, build_model_string


def test_load_presets_returns_list_of_debaters():
    presets = load_presets()
    assert len(presets) == 3
    # Preset names are in Chinese (see presets.yaml)
    assert presets[0].name == "质疑者"
    assert presets[1].name == "乐观派"
    assert presets[2].name == "分析家"


def test_settings_defaults():
    settings = Settings()
    assert settings.api_base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-chat"
    assert settings.api_key == os.environ.get("DEEPSEEK_API_KEY", "")


def test_build_model_string_deepseek():
    result = build_model_string("https://api.deepseek.com", "deepseek-chat")
    assert result == "deepseek:deepseek-chat"


def test_build_model_string_openai():
    result = build_model_string("https://api.openai.com/v1", "gpt-4o")
    assert result == "openai:gpt-4o"


def test_build_model_string_unknown_provider():
    result = build_model_string("https://my-custom-api.com/v1", "my-model")
    assert result == "openai:my-model"

"""Tests for PydanticAI agent factories (model config, tools, thinking).

Prompt-content/assembly behavior is tested in tests/test_prompts_module.py;
this file only verifies the thin adapter layer in app/agents.py.
"""
from unittest.mock import MagicMock, patch

from pydantic_ai.models import Model

from app.agents import (
    create_debater_agent,
    create_extractor_agent,
    create_judge_agent,
    create_topic_refiner_agent,
    create_topic_suggester_agent,
)
from app.engine.state import DebaterDeps
from app.models import Debater


def _mock_model():
    """Create a mock that passes isinstance(model, Model) check."""
    return MagicMock(spec=Model)


def test_create_debater_agent_returns_agent():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_create_judge_agent_returns_agent():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_create_extractor_agent_returns_agent():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_debater_agent_has_web_search_tool():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" in tool_names


def test_judge_agent_has_no_web_search_tool():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" not in tool_names


def test_debater_agent_without_search_has_no_web_search_tool():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent(
            "deepseek-chat", "https://api.example.com", "test-key", enable_search=False
        )
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" not in tool_names


def test_debater_agent_has_thinking_enabled():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings["extra_body"]["thinking"]["type"] == "enabled"


def test_debater_agent_no_search_has_thinking_enabled():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent(
            "deepseek-chat", "https://api.example.com", "test-key", enable_search=False
        )
    settings = agent.model_settings or {}
    assert settings["extra_body"]["thinking"]["type"] == "enabled"


def test_judge_agent_disables_thinking_via_extra_body():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings["extra_body"]["thinking"]["type"] == "disabled"


def test_extractor_agent_has_no_tools():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert len(tool_names) == 0


def test_extractor_agent_disables_thinking_via_extra_body():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings.get("thinking") is not True
    assert settings["extra_body"]["thinking"]["type"] == "disabled"


def test_topic_refiner_agent_disables_thinking_and_caps_tokens():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_topic_refiner_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings["max_tokens"] == 512
    assert settings["temperature"] == 0.7
    assert settings["extra_body"]["thinking"]["type"] == "disabled"


def test_topic_suggester_agent_returns_list_and_is_spicier():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_topic_suggester_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent.output_type == list[str]
    settings = agent.model_settings or {}
    assert settings["max_tokens"] == 512
    assert settings["temperature"] == 0.9
    assert settings["extra_body"]["thinking"]["type"] == "disabled"


def test_debater_deps_dataclass():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(topic="AI ethics", debater=debater, round_number=1, max_rounds=5)
    assert deps.topic == "AI ethics"
    assert deps.debater.name == "Test"
    assert deps.round_number == 1
    assert deps.max_rounds == 5


def test_debater_deps_brave_api_key_defaults_none():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(topic="AI ethics", debater=debater, round_number=1, max_rounds=5)
    assert deps.brave_api_key is None

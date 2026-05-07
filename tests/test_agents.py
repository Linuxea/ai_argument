import pytest
from unittest.mock import MagicMock, patch

from pydantic_ai.models import Model
from agents import (
    create_debater_agent,
    create_debater_agent_no_search,
    create_judge_agent,
    create_extractor_agent,
    DebaterDeps,
    DEBATE_RULES,
    STANCE_INSTRUCTIONS,
    JUDGE_PROMPT,
    _build_debater_instructions,
    CONCESSION_INSTRUCTIONS,
    STRATEGY_INSTRUCTIONS,
    MEMORY_INSTRUCTIONS,
    EXTRACT_POINTS_PROMPT,
)
from models import Debater


def _mock_model():
    """Create a mock that passes isinstance(model, Model) check."""
    return MagicMock(spec=Model)


def test_create_debater_agent_returns_agent():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_create_judge_agent_returns_agent():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_build_debater_instructions_contains_rules():
    debater = Debater(name="Test", personality="You are a test debater.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="AI in education",
        debater=debater,
        round_number=0,
        max_rounds=None,
    )

    instructions = _build_debater_instructions(ctx)

    assert "multi-party debate" in instructions
    assert "You are a test debater." in instructions
    assert "balanced view" in instructions


def test_build_debater_instructions_with_for_stance():
    debater = Debater(
        name="Optimist",
        stance="正方",
        personality="Be optimistic.",
    )
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="Test topic",
        debater=debater,
        round_number=0,
        max_rounds=3,
    )

    instructions = _build_debater_instructions(ctx)

    assert "support the topic" in instructions
    assert "This is round 1 of 3" in instructions


def test_build_debater_instructions_final_round():
    debater = Debater(
        name="Skeptic",
        stance="反方",
        personality="Be skeptical.",
    )
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="Test topic",
        debater=debater,
        round_number=2,
        max_rounds=3,
    )

    instructions = _build_debater_instructions(ctx)

    assert "FINAL ROUND" in instructions
    assert "oppose the topic" in instructions


def test_debater_deps_dataclass():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(
        topic="AI ethics",
        debater=debater,
        round_number=1,
        max_rounds=5,
    )
    assert deps.topic == "AI ethics"
    assert deps.debater.name == "Test"
    assert deps.round_number == 1
    assert deps.max_rounds == 5


def test_debater_deps_with_brave_api_key():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(
        topic="AI ethics",
        debater=debater,
        round_number=1,
        max_rounds=5,
        brave_api_key="test-key-123",
    )
    assert deps.brave_api_key == "test-key-123"


def test_debater_deps_brave_api_key_defaults_none():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(
        topic="AI ethics",
        debater=debater,
        round_number=1,
        max_rounds=5,
    )
    assert deps.brave_api_key is None


def test_debater_agent_has_web_search_tool():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" in tool_names


def test_judge_agent_has_no_web_search_tool():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" not in tool_names


def test_debater_agent_has_thinking_enabled():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent.model_settings.get("thinking") is True


def test_debater_agent_no_search_has_thinking_enabled():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent_no_search("deepseek-chat", "https://api.example.com", "test-key")
    assert agent.model_settings.get("thinking") is True


def test_judge_agent_does_not_have_thinking_enabled():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings.get("thinking") is not True


def test_concession_instructions_exists():
    assert isinstance(CONCESSION_INSTRUCTIONS, str)
    assert len(CONCESSION_INSTRUCTIONS) > 50
    assert "退让" in CONCESSION_INSTRUCTIONS


def test_strategy_instructions_exists():
    assert isinstance(STRATEGY_INSTRUCTIONS, str)
    assert len(STRATEGY_INSTRUCTIONS) > 50
    assert "strategy" in STRATEGY_INSTRUCTIONS.lower()


def test_memory_instructions_exists():
    assert isinstance(MEMORY_INSTRUCTIONS, str)
    assert len(MEMORY_INSTRUCTIONS) > 50
    assert "reference" in MEMORY_INSTRUCTIONS.lower() or "earlier" in MEMORY_INSTRUCTIONS.lower()


def test_extract_points_prompt_exists():
    assert isinstance(EXTRACT_POINTS_PROMPT, str)
    assert "points" in EXTRACT_POINTS_PROMPT.lower()
    assert "json" in EXTRACT_POINTS_PROMPT.lower()


def test_build_debater_instructions_includes_concession_for_round_2():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=1, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "退让" in instructions


def test_build_debater_instructions_excludes_concession_for_round_0():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=0, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "退让" not in instructions


def test_build_debater_instructions_includes_strategy_for_round_2():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=1, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Dynamic Strategy" in instructions


def test_build_debater_instructions_includes_memory_for_round_2():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=2, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Memory and Citation" in instructions


def test_build_debater_instructions_excludes_new_instructions_for_round_0():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=0, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Dynamic Strategy" not in instructions
    assert "Memory and Citation" not in instructions


def test_create_extractor_agent_returns_agent():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_extractor_agent_has_no_tools():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert len(tool_names) == 0


def test_extractor_agent_has_no_thinking():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings.get("thinking") is not True

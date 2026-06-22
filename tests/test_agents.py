import pytest
from unittest.mock import MagicMock, patch

from pydantic_ai.models import Model
from app.agents import (
    create_debater_agent,
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
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" in tool_names


def test_judge_agent_has_no_web_search_tool():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" not in tool_names


def test_debater_agent_has_thinking_enabled():
    """Debater agent configures ``thinking: True`` in model_settings.

    NOTE: This only verifies the Python dict on the Agent instance. PydanticAI
    1.x's capability layer does NOT forward the unified ``thinking`` field to
    the OpenAI SDK on the OpenAIModel path (verified by intercepting
    ``AsyncCompletions.create``: HTTP body has no ``reasoning_effort`` and no
    ``extra_body.thinking``). In production, debater thinking is effectively ON
    only because DeepSeek V4 ships with ``thinking.type=enabled`` as the
    provider default. If that default ever changes, debater will silently lose
    reasoning — to control it reliably, switch to
    ``model_settings={'extra_body': {'thinking': {'type': 'enabled'}}, ...}``
    like the extractor agent does (in reverse).
    """
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent.model_settings.get("thinking") is True


def test_debater_agent_no_search_has_thinking_enabled():
    """Same caveat as test_debater_agent_has_thinking_enabled applies."""
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key", enable_search=False)
    assert agent.model_settings.get("thinking") is True


def test_debater_agent_without_search_has_no_web_search_tool():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key", enable_search=False)
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" not in tool_names


def test_judge_agent_does_not_have_thinking_enabled():
    """Judge agent does not set the unified ``thinking`` field.

    NOTE: This only inspects the Python dict, not the actual HTTP request.
    Because PydanticAI 1.x does not forward the unified ``thinking`` field on
    the OpenAIModel path AND the judge agent doesn't set ``extra_body`` either,
    the judge's effective thinking behavior is determined entirely by the
    DeepSeek V4 provider default — which is currently ``enabled``. So despite
    the test name, the judge DOES run thinking in production. Switch the
    assertion or the agent config if you want to make this deterministic.
    """
    with patch("app.agents._make_model", return_value=_mock_model()):
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
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_extractor_agent_has_no_tools():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert len(tool_names) == 0


def test_extractor_agent_disables_thinking_via_extra_body():
    """Extractor explicitly disables thinking through ``extra_body``.

    Unlike the unified ``thinking`` field (silently dropped by PydanticAI 1.x
    on the OpenAIModel path), ``extra_body`` IS forwarded to the upstream API,
    so this is the configuration that actually controls HTTP behavior.
    Verified end-to-end: with this setting, extractor latency drops ~62%
    and output tokens ~86% versus the DeepSeek V4 thinking-enabled default.
    """
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings.get("thinking") is not True
    assert settings["extra_body"]["thinking"]["type"] == "disabled"

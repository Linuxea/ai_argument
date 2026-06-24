from unittest.mock import MagicMock, patch

from pydantic_ai.models import Model

from app.agents import (
    EXTRACT_POINTS_PROMPT,
    MEMORY_INSTRUCTIONS,
    SEARCH_INSTRUCTIONS,
    SEARCH_OPENING_INSTRUCTIONS,
    STRATEGY_INSTRUCTIONS,
    _build_debater_instructions,
    create_debater_agent,
    create_extractor_agent,
    create_judge_agent,
    create_topic_refiner_agent,
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
    assert "balanced, analytical view" in instructions
    # Personality is framed as the authoritative voice/tone persona so that
    # a playful/contrarian character isn't overruled by generic "be
    # professional" rules.
    assert "HIGHEST priority" in instructions
    assert "in character" in instructions


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

    assert "SUPPORT the topic" in instructions
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
    assert "OPPOSE the topic" in instructions


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
    """Debater thinking is enabled via ``extra_body.thinking.type=enabled``.

    The unified ``thinking`` field in ModelSettings is silently dropped by
    PydanticAI 1.x's capability layer on the OpenAI-compatible path, so
    ``extra_body`` is the only reliably-forwarded mechanism. We verify the
    dict on the Agent instance (full HTTP-level verification would require
    intercepting AsyncCompletions.create, which is covered by an integration
    test, not a unit test).
    """
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings["extra_body"]["thinking"]["type"] == "enabled"


def test_debater_agent_no_search_has_thinking_enabled():
    """Same as test_debater_agent_has_thinking_enabled for the no-search variant."""
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent(
            "deepseek-chat", "https://api.example.com", "test-key", enable_search=False
        )
    settings = agent.model_settings or {}
    assert settings["extra_body"]["thinking"]["type"] == "enabled"


def test_debater_agent_without_search_has_no_web_search_tool():
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent(
            "deepseek-chat", "https://api.example.com", "test-key", enable_search=False
        )
    tool_names = list(agent._function_toolset.tools.keys())
    assert "web_search" not in tool_names


def test_judge_agent_disables_thinking_via_extra_body():
    """Judge thinking is explicitly disabled via ``extra_body`` for bounded latency.

    Standardising on ``extra_body`` (instead of the unified ``thinking`` field
    that PydanticAI 1.x silently drops) makes the judge's behaviour
    deterministic regardless of provider defaults.
    """
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings["extra_body"]["thinking"]["type"] == "disabled"


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


def test_topic_refiner_agent_disables_thinking_and_caps_tokens():
    """M2: topic refinement runs through a PydanticAI Agent with bounded
    max_tokens and thinking disabled (refinement is a paraphrase, not a
    reasoning task). Verified at the model_settings level.
    """
    with patch("app.agents._make_model", return_value=_mock_model()):
        agent = create_topic_refiner_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings["max_tokens"] == 512
    assert settings["temperature"] == 0.7
    assert settings["extra_body"]["thinking"]["type"] == "disabled"


def test_search_instructions_exists():
    assert isinstance(SEARCH_INSTRUCTIONS, str)
    assert len(SEARCH_INSTRUCTIONS) > 50
    assert "Conservation Mode" in SEARCH_INSTRUCTIONS


def test_search_opening_instructions_exists():
    assert isinstance(SEARCH_OPENING_INSTRUCTIONS, str)
    assert len(SEARCH_OPENING_INSTRUCTIONS) > 50
    assert "Opening Round" in SEARCH_OPENING_INSTRUCTIONS


def test_search_opening_used_in_round_0():
    """Round 0 (first turn) uses SEARCH_OPENING_INSTRUCTIONS, not SEARCH_INSTRUCTIONS."""
    debater = Debater(name="Test", stance="正方", personality="Test.", enable_search=True)
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=0, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Opening Round" in instructions
    assert "Conservation Mode" not in instructions


def test_search_conservation_used_in_round_1():
    """Round 1+ uses SEARCH_INSTRUCTIONS (conservation mode), not the opening variant."""
    debater = Debater(name="Test", stance="正方", personality="Test.", enable_search=True)
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=1, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Conservation Mode" in instructions
    assert "Opening Round" not in instructions


def test_search_disabled_skips_both():
    """When enable_search=False, neither search prompt appears."""
    debater = Debater(name="Test", stance="正方", personality="Test.", enable_search=False)
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=0, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Opening Round" not in instructions
    assert "Conservation Mode" not in instructions
    assert "Web Search" not in instructions

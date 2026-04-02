import pytest
from unittest.mock import MagicMock

from agents import (
    create_debater_agent,
    create_judge_agent,
    DebaterDeps,
    DEBATE_RULES,
    STANCE_INSTRUCTIONS,
    JUDGE_PROMPT,
    _build_debater_instructions,
)
from models import Debater


def test_create_debater_agent_returns_agent():
    agent = create_debater_agent("deepseek:deepseek-chat")
    assert agent is not None


def test_create_judge_agent_returns_agent():
    agent = create_judge_agent("deepseek:deepseek-chat")
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
        stance="for",
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
        stance="against",
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

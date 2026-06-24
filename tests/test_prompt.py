"""Tests for build_debater_user_prompt — no engine/agent construction."""
from app.engine.state import DebateState, Message
from app.models import ArgumentSummary, Debater
from app.prompts import build_debater_user_prompt


def _debater(**kw):
    return Debater(name="A", personality="x", **kw)


def test_first_turn_marks_opening():
    state = DebateState(topic="Should AI replace teachers?", debaters=[_debater()])
    prompt = build_debater_user_prompt(state, _debater())
    assert "first speaker" in prompt
    assert "Should AI replace teachers?" in prompt
    assert "<topic>" in prompt


def test_excludes_own_messages():
    skeptic = Debater(name="Skeptic", personality="x")
    state = DebateState(
        topic="AI in education",
        debaters=[skeptic, Debater(name="Optimist", personality="y")],
        history=[
            Message(speaker="Skeptic", content="Teachers are irreplaceable."),
            Message(speaker="Optimist", content="AI can enhance learning."),
        ],
    )
    prompt = build_debater_user_prompt(state, skeptic)
    assert "Teachers are irreplaceable." not in prompt
    assert "AI can enhance learning." in prompt


def test_includes_argument_summaries():
    state = DebateState(
        topic="T",
        debaters=[_debater()],
        history=[Message(speaker="B", content="hello")],
        argument_summaries=[ArgumentSummary(round=0, debater_name="B", points=["claim one"])],
    )
    prompt = build_debater_user_prompt(state, _debater())
    assert "[Key arguments raised so far]:" in prompt
    assert "claim one" in prompt


def test_user_messages_are_fenced():
    skeptic = Debater(name="Skeptic", personality="x")
    state = DebateState(
        topic="T",
        debaters=[skeptic],
        history=[Message(speaker="You", content=" injected ")],
    )
    prompt = build_debater_user_prompt(state, skeptic)
    assert "<user_message> injected </user_message>" in prompt


def test_round_countdown_final_round():
    state = DebateState(topic="T", debaters=[_debater()], current_round=2, max_rounds=3)
    prompt = build_debater_user_prompt(state, _debater(enable_search=False))
    assert "FINAL ROUND" in prompt
    assert "No holding back" in prompt


def test_round_countdown_remaining_plural():
    state = DebateState(topic="T", debaters=[_debater()], current_round=0, max_rounds=3)
    prompt = build_debater_user_prompt(state, _debater(enable_search=False))
    assert "This is round 1 of 3" in prompt
    assert "are 2 rounds remaining" in prompt


def test_round_countdown_remaining_singular():
    state = DebateState(topic="T", debaters=[_debater()], current_round=1, max_rounds=3)
    prompt = build_debater_user_prompt(state, _debater(enable_search=False))
    assert "is 1 round remaining" in prompt


def test_no_countdown_when_unlimited():
    state = DebateState(topic="T", debaters=[_debater()], current_round=2, max_rounds=None)
    prompt = build_debater_user_prompt(state, _debater(enable_search=False))
    assert "This is round" not in prompt
    assert "FINAL" not in prompt


def test_opening_search_guidance_round0():
    state = DebateState(topic="T", debaters=[_debater()], current_round=0, max_rounds=3)
    prompt = build_debater_user_prompt(state, _debater(enable_search=True))
    assert "opening round" in prompt.lower()
    assert "2-4 times" in prompt


def test_no_opening_guidance_when_search_disabled():
    state = DebateState(topic="T", debaters=[_debater()], current_round=0, max_rounds=3)
    prompt = build_debater_user_prompt(state, _debater(enable_search=False))
    assert "opening round" not in prompt.lower()

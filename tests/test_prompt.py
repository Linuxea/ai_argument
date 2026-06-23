"""Pure-function tests for build_user_prompt — no engine/agent construction."""
from app.engine.prompt import build_user_prompt
from app.engine.state import DebateState, Message
from app.models import ArgumentSummary, Debater


def test_build_user_prompt_first_turn():
    state = DebateState(topic="Should AI replace teachers?", debaters=[Debater(name="A", personality="x")])
    prompt = build_user_prompt(state, Debater(name="A", personality="x"))
    assert "first speaker" in prompt
    assert "Should AI replace teachers?" in prompt
    assert "<topic>" in prompt


def test_build_user_prompt_excludes_own_messages():
    skeptic = Debater(name="Skeptic", personality="x")
    state = DebateState(
        topic="AI in education",
        debaters=[skeptic, Debater(name="Optimist", personality="y")],
        history=[
            Message(speaker="Skeptic", content="Teachers are irreplaceable."),
            Message(speaker="Optimist", content="AI can enhance learning."),
        ],
    )
    prompt = build_user_prompt(state, skeptic)
    assert "Teachers are irreplaceable." not in prompt  # own message excluded
    assert "AI can enhance learning." in prompt          # others included


def test_build_user_prompt_includes_argument_summaries():
    state = DebateState(
        topic="T",
        debaters=[Debater(name="A", personality="x")],
        history=[Message(speaker="B", content="hello")],
        argument_summaries=[ArgumentSummary(round=0, debater_name="B", points=["claim one"])],
    )
    prompt = build_user_prompt(state, Debater(name="A", personality="x"))
    assert "[Key arguments raised so far]:" in prompt
    assert "claim one" in prompt

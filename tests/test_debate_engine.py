# tests/test_debate_engine.py
import pytest
from debate_engine import DebateEngine, DebateState, Message
from models import Debater
from tests.conftest import MockLLMClient


def test_build_messages_starts_with_system_and_topic():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(
        name="Test Debater",
        personality="You are a test debater."
    )
    engine.state = DebateState(
        topic="Should AI replace teachers?",
        debaters=[debater]
    )

    messages = engine.build_messages(debater)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a test debater."
    assert messages[1]["role"] == "user"
    assert "Should AI replace teachers?" in messages[1]["content"]


def test_build_messages_assigns_correct_roles():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")

    engine.state = DebateState(
        topic="AI in education",
        debaters=[skeptic, optimist],
        history=[
            Message(speaker="Skeptic", content="Teachers are irreplaceable."),
            Message(speaker="Optimist", content="AI can enhance learning."),
            Message(speaker="You", content="What about special needs?"),
        ]
    )

    # Build messages for Skeptic
    messages = engine.build_messages(skeptic)

    # Skeptic's own message should be "assistant"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "Teachers are irreplaceable."

    # Optimist's message should be "user" with prefix
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "[Optimist]: AI can enhance learning."

    # User's message should be "user" with prefix
    assert messages[4]["role"] == "user"
    assert messages[4]["content"] == "[You]: What about special needs?"


def test_advance_turn_round_robin():
    mock_llm = MockLLMClient(responses=["Response A", "Response B"])
    engine = DebateEngine(llm_client=mock_llm)

    debater_a = Debater(name="A", personality="You are A.")
    debater_b = Debater(name="B", personality="You are B.")

    engine.state = DebateState(
        topic="Test topic",
        debaters=[debater_a, debater_b]
    )

    assert engine.state.current_turn_index == 0
    assert engine.state.current_round == 0

    # After first turn, should advance to B (index 1)
    engine._advance_turn()
    assert engine.state.current_turn_index == 1
    assert engine.state.current_round == 0

    # After second turn, should wrap to A (index 0) and increment round
    engine._advance_turn()
    assert engine.state.current_turn_index == 0
    assert engine.state.current_round == 1


def test_inject_message_adds_to_history():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    engine.inject_message("This is my comment.")

    assert len(engine.state.history) == 1
    assert engine.state.history[0].speaker == "You"
    assert engine.state.history[0].content == "This is my comment."


def test_stop_sets_inactive():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    engine.stop()

    assert engine.state.active is False


def test_resume_sets_active():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    engine.resume()

    assert engine.state.active is True

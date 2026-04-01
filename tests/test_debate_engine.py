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
    assert "You are a test debater." in messages[0]["content"]
    assert "multi-party debate" in messages[0]["content"]
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


# Tests for input validation in start()
def test_start_raises_error_on_empty_debaters():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    with pytest.raises(ValueError, match="debaters list cannot be empty"):
        engine.start(topic="Test topic", debaters=[])


def test_start_raises_error_on_zero_max_rounds():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")

    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        engine.start(topic="Test topic", debaters=[debater], max_rounds=0)


def test_start_raises_error_on_negative_max_rounds():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")

    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        engine.start(topic="Test topic", debaters=[debater], max_rounds=-1)


# Tests for boolean return values
def test_inject_message_returns_true_when_state_exists():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    result = engine.inject_message("Test message")

    assert result is True


def test_inject_message_returns_false_when_no_state():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    result = engine.inject_message("Test message")

    assert result is False


def test_stop_returns_true_when_state_exists():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    result = engine.stop()

    assert result is True


def test_stop_returns_false_when_no_state():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    result = engine.stop()

    assert result is False


def test_resume_returns_true_when_state_exists():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    result = engine.resume()

    assert result is True


def test_resume_returns_false_when_no_state():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    result = engine.resume()

    assert result is False


# Tests for async methods
@pytest.mark.asyncio
async def test_run_turn_emits_correct_events():
    mock_llm = MockLLMClient(responses=["Hello world from debater."])
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Alice", personality="You are Alice.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    await engine.run_turn()

    # Check events were emitted
    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "debater_start" in event_types
    assert "debater_chunk" in event_types
    assert "debater_end" in event_types

    # Verify debater_start payload
    start_event = next(e for e in events if e.type == "debater_start")
    assert start_event.payload["debater_name"] == "Alice"

    # Verify debater_end payload
    end_event = next(e for e in events if e.type == "debater_end")
    assert end_event.payload["debater_name"] == "Alice"
    assert "Hello world from debater." in end_event.payload["full_text"]


@pytest.mark.asyncio
async def test_run_turn_adds_message_to_history():
    mock_llm = MockLLMClient(responses=["This is my argument."])
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Bob", personality="You are Bob.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    await engine.run_turn()

    assert len(engine.state.history) == 1
    assert engine.state.history[0].speaker == "Bob"
    assert "This is my argument." in engine.state.history[0].content


@pytest.mark.asyncio
async def test_run_turn_does_nothing_when_state_is_none():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    # Don't set state

    await engine.run_turn()

    # Should not raise error and queue should be empty
    assert engine.event_queue.empty()


@pytest.mark.asyncio
async def test_run_turn_does_nothing_when_not_active():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    await engine.run_turn()

    # Should not have called LLM or added events
    assert engine.event_queue.empty()
    assert len(engine.state.history) == 0


@pytest.mark.asyncio
async def test_run_loop_respects_max_rounds():
    mock_llm = MockLLMClient(responses=["Argument 1", "Argument 2"])
    engine = DebateEngine(llm_client=mock_llm)

    debater_a = Debater(name="A", personality="You are A.")
    debater_b = Debater(name="B", personality="You are B.")

    engine.state = DebateState(
        topic="Test topic",
        debaters=[debater_a, debater_b],
        max_rounds=2
    )

    await engine.run_loop()

    # With max_rounds=2 and 2 debaters, we should have 4 turns total
    assert engine.state.current_round == 2
    assert engine.state.active is False

    # Check that debate_end event was emitted
    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    end_events = [e for e in events if e.type == "debate_end"]
    assert len(end_events) == 1
    assert "Max rounds reached" in end_events[0].payload["reason"]


@pytest.mark.asyncio
async def test_run_loop_emits_round_end_event():
    mock_llm = MockLLMClient(responses=["Arg"])
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Solo", personality="Solo debater.")
    engine.state = DebateState(
        topic="Test topic",
        debaters=[debater],
        max_rounds=2
    )

    await engine.run_loop()

    # Collect events
    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    round_end_events = [e for e in events if e.type == "round_end"]
    # Should have 2 round_end events (round 1 and round 2)
    assert len(round_end_events) == 2


@pytest.mark.asyncio
async def test_run_loop_stops_when_debate_stopped():
    mock_llm = MockLLMClient(responses=["Response"])
    engine = DebateEngine(llm_client=mock_llm)

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    # Stop the debate before running loop
    engine.stop()

    await engine.run_loop()

    # Should not have processed any turns
    assert len(engine.state.history) == 0


@pytest.mark.asyncio
async def test_judge_returns_true_when_state_exists():
    mock_llm = MockLLMClient(responses=["My judgment is..."])
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    result = await engine.judge()

    assert result is True


@pytest.mark.asyncio
async def test_judge_returns_false_when_no_state():
    mock_llm = MockLLMClient()
    engine = DebateEngine(llm_client=mock_llm)

    result = await engine.judge()

    assert result is False


@pytest.mark.asyncio
async def test_judge_emits_correct_events():
    mock_llm = MockLLMClient(responses=["The winner is..."])
    engine = DebateEngine(llm_client=mock_llm)
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    await engine.judge()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "judge_chunk" in event_types
    assert "judge_result" in event_types

    judge_result = next(e for e in events if e.type == "judge_result")
    assert "The winner is..." in judge_result.payload["judgment_text"]

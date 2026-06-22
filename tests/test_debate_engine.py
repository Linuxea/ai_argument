# tests/test_debate_engine.py
import asyncio
from unittest.mock import MagicMock

import pytest

from app.engine.debate import DebateEngine
from app.engine.state import DebateState, Message
from app.models import Debater, ArgumentSummary
from tests.conftest import MockDebateAgent


def _make_engine(responses=None):
    """Create a DebateEngine with mocked agents."""
    import asyncio

    mock = MockDebateAgent(responses=responses)
    engine = object.__new__(DebateEngine)
    engine.model = "test:model"
    engine.base_url = None
    engine.api_key = None
    engine.brave_api_key = ""
    engine.debater_agent = mock
    engine.debater_agent_no_search = mock
    engine.judge_agent = MockDebateAgent(responses=responses or ["Judgment."])
    engine._extractor_agent = MockDebateAgent(responses=['{"points": ["mock claim"]}'])
    engine.state = None
    engine.event_queue = asyncio.Queue()
    engine.event_log = []
    engine._event_log_max = 500
    engine._next_event_id = 1
    engine._loop_task = None
    engine.judge_task = None
    engine._history = {}
    engine._extraction_tasks = set()
    engine._consumer_active = False
    return engine, mock


def test_build_user_prompt_first_turn():
    engine, _ = _make_engine()
    debater = Debater(name="Test Debater", personality="You are a test debater.")
    engine.state = DebateState(topic="Should AI replace teachers?", debaters=[debater])

    prompt = engine._build_user_prompt(debater)

    assert "first speaker" in prompt
    assert "Should AI replace teachers?" in prompt


def test_build_user_prompt_subsequent_turn():
    engine, _ = _make_engine()
    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")

    engine.state = DebateState(
        topic="AI in education",
        debaters=[skeptic, optimist],
        history=[
            Message(speaker="Skeptic", content="Teachers are irreplaceable."),
            Message(speaker="Optimist", content="AI can enhance learning."),
            Message(speaker="You", content="What about special needs?"),
        ],
    )

    prompt = engine._build_user_prompt(skeptic)

    # Skeptic's own messages should be excluded
    assert "Teachers are irreplaceable." not in prompt
    # Other speakers should appear
    assert "[Optimist]: AI can enhance learning." in prompt
    assert "[You]: What about special needs?" in prompt
    # Topic is fenced so injected content can't pose as instructions.
    assert "<topic>AI in education</topic>" in prompt


def test_advance_turn_round_robin():
    engine, _ = _make_engine(responses=["Response A", "Response B"])

    debater_a = Debater(name="A", personality="You are A.")
    debater_b = Debater(name="B", personality="You are B.")

    engine.state = DebateState(topic="Test topic", debaters=[debater_a, debater_b])

    assert engine.state.current_turn_index == 0
    assert engine.state.current_round == 0

    engine._advance_turn()
    assert engine.state.current_turn_index == 1
    assert engine.state.current_round == 0

    engine._advance_turn()
    assert engine.state.current_turn_index == 0
    assert engine.state.current_round == 1


def test_inject_message_adds_to_history():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    engine.inject_message("This is my comment.")

    assert len(engine.state.history) == 1
    assert engine.state.history[0].speaker == "You"
    assert engine.state.history[0].content == "This is my comment."


def test_stop_sets_inactive():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    engine.stop()

    assert engine.state.active is False


def test_resume_sets_active():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    engine.resume()

    assert engine.state.active is True


def test_start_raises_error_on_empty_debaters():
    engine, _ = _make_engine()

    with pytest.raises(ValueError, match="debaters list cannot be empty"):
        engine.start(topic="Test topic", debaters=[])


def test_start_rejects_duplicate_names():
    """C1: same-named debaters must be rejected at the engine boundary too,
    not just at the API layer. Otherwise they share one message_history slot
    and silently talk to themselves."""
    engine, _ = _make_engine()
    a = Debater(name="Alice", personality="p")
    b = Debater(name="Alice", personality="p2")
    with pytest.raises(ValueError, match="unique names"):
        engine.start(topic="t", debaters=[a, b])


@pytest.mark.asyncio
async def test_start_cancels_lingering_extraction_tasks():
    """M11: extraction tasks are fire-and-forget but tracked; start() must
    cancel stragglers from a prior debate so they don't append stale
    summaries to the new debate's state."""
    engine, _ = _make_engine()
    # Use mocks instead of real tasks so cancellation is synchronous and
    # observable in the assertion.
    t1 = MagicMock()
    t2 = MagicMock()
    engine._extraction_tasks = {t1, t2}

    a = Debater(name="Alice", personality="p")
    b = Debater(name="Bob", personality="p")
    engine.start(topic="t", debaters=[a, b])

    t1.cancel.assert_called_once()
    t2.cancel.assert_called_once()
    assert engine._extraction_tasks == set()
    assert engine._consumer_active is False


@pytest.mark.asyncio
async def test_emit_error_routes_through_emit_and_assigns_event_type():
    """emit_error is the public terminal-error helper used by routes. It must
    route through _emit (so replay buffer captures it) and pick the right
    event type based on the ``judge`` flag."""
    engine, _ = _make_engine()
    engine.event_queue = __import__("asyncio").Queue()

    await engine.emit_error("oops", judge=False)
    await engine.emit_error("judge oops", judge=True)

    events: list = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())
    types = [e.type for e in events]
    assert types == ["debate_error", "judge_error"]
    # Both events got replay-buffer ids (proves they went through _emit).
    assert all(e.id > 0 for e in events)
    assert len(engine.event_log) == 2


def test_acquire_consumer_enforces_single_slot():
    """M5: a second concurrent consumer must be rejected so events aren't
    split between two waiters on event_queue.get()."""
    engine, _ = _make_engine()
    assert engine.acquire_consumer() is True   # first caller wins
    assert engine.acquire_consumer() is False  # second is rejected
    engine.release_consumer()
    # Slot is free again.
    assert engine.acquire_consumer() is True
    engine.release_consumer()


def test_release_consumer_idempotent():
    """Releasing when not held must not error."""
    engine, _ = _make_engine()
    engine.release_consumer()  # no-op
    engine.release_consumer()  # still no-op
    assert engine.acquire_consumer() is True


def test_start_raises_error_on_zero_max_rounds():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")

    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        engine.start(topic="Test topic", debaters=[debater], max_rounds=0)


def test_start_raises_error_on_negative_max_rounds():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")

    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        engine.start(topic="Test topic", debaters=[debater], max_rounds=-1)


def test_inject_message_returns_true_when_state_exists():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    result = engine.inject_message("Test message")

    assert result is True


def test_inject_message_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = engine.inject_message("Test message")

    assert result is False


def test_stop_returns_true_when_state_exists():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    result = engine.stop()

    assert result is True


def test_stop_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = engine.stop()

    assert result is False


def test_resume_returns_true_when_state_exists():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    result = engine.resume()

    assert result is True


def test_resume_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = engine.resume()

    assert result is False


def test_start_initializes_per_debater_history():
    engine, _ = _make_engine()
    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")

    engine.start(topic="Test", debaters=[skeptic, optimist])

    assert "Skeptic" in engine._history
    assert "Optimist" in engine._history
    assert engine._history["Skeptic"] == []
    assert engine._history["Optimist"] == []


@pytest.mark.asyncio
async def test_run_turn_emits_correct_events():
    engine, mock = _make_engine(responses=["Hello world from debater."])

    debater = Debater(name="Alice", personality="You are Alice.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Alice": []}  # Initialize per-debater history

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "debater_start" in event_types
    assert "debater_chunk" in event_types
    assert "debater_end" in event_types

    start_event = next(e for e in events if e.type == "debater_start")
    assert start_event.payload["debater_name"] == "Alice"

    end_event = next(e for e in events if e.type == "debater_end")
    assert end_event.payload["debater_name"] == "Alice"
    assert "Hello world from debater." in end_event.payload["full_text"]


@pytest.mark.asyncio
async def test_run_turn_adds_message_to_history():
    engine, mock = _make_engine(responses=["This is my argument."])

    debater = Debater(name="Bob", personality="You are Bob.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Bob": []}  # Initialize per-debater history

    await engine.run_turn()

    assert len(engine.state.history) == 1
    assert engine.state.history[0].speaker == "Bob"
    assert "This is my argument." in engine.state.history[0].content


@pytest.mark.asyncio
async def test_run_turn_does_nothing_when_state_is_none():
    engine, _ = _make_engine()

    await engine.run_turn()

    assert engine.event_queue.empty()


@pytest.mark.asyncio
async def test_run_turn_does_nothing_when_not_active():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    await engine.run_turn()

    assert engine.event_queue.empty()
    assert len(engine.state.history) == 0


@pytest.mark.asyncio
async def test_run_loop_respects_max_rounds():
    engine, _ = _make_engine(responses=["Argument 1", "Argument 2"])

    debater_a = Debater(name="A", personality="You are A.")
    debater_b = Debater(name="B", personality="You are B.")

    engine.state = DebateState(
        topic="Test topic", debaters=[debater_a, debater_b], max_rounds=2
    )
    engine._history = {"A": [], "B": []}  # Initialize per-debater history

    await engine.run_loop()

    assert engine.state.current_round == 2
    assert engine.state.active is False

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    end_events = [e for e in events if e.type == "debate_end"]
    assert len(end_events) == 1
    assert "Max rounds reached" in end_events[0].payload["reason"]


@pytest.mark.asyncio
async def test_run_loop_emits_round_end_event():
    engine, _ = _make_engine(responses=["Arg"])

    debater = Debater(name="Solo", personality="Solo debater.")
    engine.state = DebateState(topic="Test topic", debaters=[debater], max_rounds=2)
    engine._history = {"Solo": []}  # Initialize per-debater history

    await engine.run_loop()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    round_end_events = [e for e in events if e.type == "round_end"]
    assert len(round_end_events) == 2


@pytest.mark.asyncio
async def test_run_loop_stops_when_debate_stopped():
    engine, _ = _make_engine(responses=["Response"])

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    engine.stop()

    await engine.run_loop()

    assert len(engine.state.history) == 0


@pytest.mark.asyncio
async def test_judge_returns_true_when_state_exists():
    engine, _ = _make_engine(responses=["My judgment is..."])

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    result = await engine.judge()

    assert result is True


@pytest.mark.asyncio
async def test_judge_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = await engine.judge()

    assert result is False


@pytest.mark.asyncio
async def test_judge_emits_correct_events():
    engine, _ = _make_engine(responses=["The winner is..."])

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


@pytest.mark.asyncio
async def test_run_turn_passes_brave_api_key_in_deps():
    engine, mock = _make_engine(responses=["I searched and found..."])
    engine.brave_api_key = "test-brave-key"

    debater = Debater(name="Alice", personality="You are Alice.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Alice": []}

    await engine.run_turn()

    deps = mock.last_kwargs.get("deps")
    assert deps is not None
    assert deps.brave_api_key == "test-brave-key"


def test_engine_stores_brave_api_key():
    engine, _ = _make_engine()
    engine.brave_api_key = "my-key"
    assert engine.brave_api_key == "my-key"


@pytest.mark.asyncio
async def test_run_turn_emits_thinking_events():
    """When the mock agent returns thinking, thinking_chunk events are emitted."""
    engine, mock = _make_engine(responses=["My argument."])
    mock.thinking = ["Let me analyze this step by step..."]

    debater = Debater(name="Thinker", personality="Deep thinker.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Thinker": []}

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "thinking_chunk" in event_types, f"Got events: {event_types}"

    thinking_events = [e for e in events if e.type == "thinking_chunk"]
    thinking_text = "".join(e.payload["text_chunk"] for e in thinking_events)
    assert "Let me analyze this step by step..." in thinking_text


@pytest.mark.asyncio
async def test_run_turn_thinking_followed_by_finalize():
    """After thinking ends, a debater_finalize event is emitted before text starts."""
    engine, mock = _make_engine(responses=["My argument."])
    mock.thinking = ["Thinking content"]

    debater = Debater(name="Thinker", personality="Deep thinker.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Thinker": []}

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "debater_finalize" in event_types, f"Got events: {event_types}"

    last_thinking_idx = max(i for i, e in enumerate(events) if e.type == "thinking_chunk")
    first_finalize_after = next(
        i for i, e in enumerate(events)
        if e.type == "debater_finalize" and i > last_thinking_idx
    )
    assert first_finalize_after > last_thinking_idx


@pytest.mark.asyncio
async def test_run_turn_no_thinking_events_without_thinking():
    """When no thinking is returned, no thinking_chunk events are emitted."""
    engine, mock = _make_engine(responses=["Just text, no thinking."])

    debater = Debater(name="Simple", personality="Simple debater.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Simple": []}

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "thinking_chunk" not in event_types


def test_argument_summary_creation():
    summary = ArgumentSummary(round=1, debater_name="Alice", points=["Claim A", "Claim B"])
    assert summary.round == 1
    assert summary.debater_name == "Alice"
    assert summary.points == ["Claim A", "Claim B"]


def test_argument_summary_default_points():
    summary = ArgumentSummary(round=0, debater_name="Bob")
    assert summary.points == []


@pytest.mark.asyncio
async def test_extract_key_points_appends_summary():
    engine, _ = _make_engine()
    engine._extractor_agent = MockDebateAgent(responses=['{"points": ["Claim A", "Claim B"]}'])
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    await engine._extract_key_points("Alice", "Some argument text", 1)

    assert len(engine.state.argument_summaries) == 1
    summary = engine.state.argument_summaries[0]
    assert summary.round == 1
    assert summary.debater_name == "Alice"
    assert summary.points == ["Claim A", "Claim B"]


@pytest.mark.asyncio
async def test_extract_key_points_handles_json_error():
    engine, _ = _make_engine()
    engine._extractor_agent = MockDebateAgent(responses=['not valid json'])
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    await engine._extract_key_points("Alice", "Some text", 1)

    assert len(engine.state.argument_summaries) == 0


@pytest.mark.asyncio
async def test_extract_key_points_handles_empty_points():
    engine, _ = _make_engine()
    engine._extractor_agent = MockDebateAgent(responses=['{"points": []}'])
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    await engine._extract_key_points("Alice", "Some text", 1)

    assert len(engine.state.argument_summaries) == 0


def test_build_user_prompt_includes_summaries():
    engine, _ = _make_engine()
    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")
    engine.state = DebateState(
        topic="AI in education",
        debaters=[skeptic, optimist],
        history=[
            Message(speaker="Skeptic", content="Teachers need empathy."),
            Message(speaker="Optimist", content="AI can personalize."),
        ],
        argument_summaries=[
            ArgumentSummary(round=0, debater_name="Skeptic", points=["Teachers need empathy"]),
            ArgumentSummary(round=0, debater_name="Optimist", points=["AI can personalize learning"]),
        ],
    )

    prompt = engine._build_user_prompt(skeptic)

    assert "Key arguments" in prompt
    assert "Skeptic" in prompt
    assert "Teachers need empathy" in prompt
    assert "Optimist" in prompt
    assert "AI can personalize learning" in prompt


def test_build_user_prompt_no_summaries_when_empty():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(
        topic="Test topic",
        debaters=[debater],
        history=[Message(speaker="Other", content="Hello")],
    )

    prompt = engine._build_user_prompt(debater)

    assert "Key arguments" not in prompt


@pytest.mark.asyncio
async def test_run_turn_calls_extract_key_points():
    engine, _ = _make_engine(responses=["My argument about AI."])
    extractor_mock = MockDebateAgent(responses=['{"points": ["AI transforms education"]}'])
    engine._extractor_agent = extractor_mock
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])
    engine._history = {"Alice": []}

    await engine.run_turn()
    # Extraction runs as a tracked fire-and-forget task; await it before
    # asserting on its side effects.
    if engine._extraction_tasks:
        await asyncio.gather(*engine._extraction_tasks, return_exceptions=True)

    assert extractor_mock.call_count == 1
    assert extractor_mock.last_user_prompt is not None
    assert "Alice" in extractor_mock.last_user_prompt
    assert len(engine.state.argument_summaries) == 1
    assert engine.state.argument_summaries[0].debater_name == "Alice"
    assert engine.state.argument_summaries[0].points == ["AI transforms education"]


# ---------------------------------------------------------------------------
# Stage 1 contracts: terminal events on failure (no client hang)
# ---------------------------------------------------------------------------


class _ExplodingAgent:
    """Agent mock whose streaming methods raise, simulating an LLM failure."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def run_stream_events(self, *_args, **_kwargs):
        raise self._exc

    def run_stream(self, *_args, **_kwargs):
        raise self._exc

    async def run(self, *_args, **_kwargs):
        raise self._exc


async def test_run_loop_failure_emits_debate_error():
    """A failure inside the loop surfaces as a debate_error terminal event."""
    engine, _ = _make_engine()
    engine.debater_agent = _ExplodingAgent(RuntimeError("provider down"))
    engine.debater_agent_no_search = _ExplodingAgent(RuntimeError("provider down"))

    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])
    engine._history = {"Alice": []}

    await engine._run_loop_and_cleanup()

    assert engine.state.active is False
    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())
    error_events = [e for e in events if e.type == "debate_error"]
    assert len(error_events) == 1
    # Generic message — provider exception text must not leak.
    assert "provider down" not in error_events[0].payload["message"]
    assert error_events[0].payload["message"]


async def test_judge_failure_emits_judge_error():
    """A failure during judging surfaces as a judge_error terminal event."""
    engine, _ = _make_engine()
    engine.judge_agent = _ExplodingAgent(RuntimeError("judge model down"))

    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    result = await engine.judge()

    assert result is False
    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())
    error_events = [e for e in events if e.type == "judge_error"]
    assert len(error_events) == 1
    # Generic message — provider exception text must not leak.
    assert "judge model down" not in error_events[0].payload["message"]
    assert error_events[0].payload["message"]

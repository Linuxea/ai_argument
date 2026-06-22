"""Extra tests to maximise coverage of small / hard-to-reach branches."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pydantic_ai import AgentRunResultEvent, FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)

from app import create_app
from app.deps import (
    DebaterRepository,
    get_debater_repository,
    get_engine,
    get_settings,
)
from app.engine.debate import DebateEngine
from app.engine.event_bus import EventBus
from app.engine.state import DebateState, Event
from app.models import Debater
from tests.conftest import MockDebateAgent


def _bare_engine() -> DebateEngine:
    """Build a DebateEngine without invoking __init__ but with the attributes
    every engine method touches initialised to safe defaults.

    Centralised so the tests don't have to keep up with attribute drift when
    we add new state to the engine (e.g. event_log, judge_task)."""
    eng = object.__new__(DebateEngine)
    eng.model = "m"
    eng.base_url = None
    eng.api_key = None
    eng.brave_api_key = ""
    eng.debater_agent = MagicMock()
    eng.debater_agent_no_search = MagicMock()
    eng.judge_agent = MagicMock()
    eng._extractor_agent = MagicMock()
    eng.state = None
    eng._events = EventBus()
    eng._loop_task = None
    eng.judge_task = None
    eng._history = {}
    eng._extraction_tasks = set()
    eng._consumer_active = False
    return eng


# ---------------------------------------------------------------------------
# app/__init__.py: easter-egg endpoint + lifespan
# ---------------------------------------------------------------------------


def test_chrome_devtools_easter_egg_endpoint():
    """The .well-known DevTools endpoint returns the hot-takes JSON payload."""
    from main import app

    client = TestClient(app)
    resp = client.get("/.well-known/appspecific/com.chrome.devtools.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body
    assert "debate_tip" in body
    assert "surprise" in body


def test_lifespan_initialises_state(monkeypatch):
    """Going through the lifespan context populates app.state.engine et al."""
    # Stub out the agent factories so we don't try to instantiate real models.
    monkeypatch.setattr("app.engine.debate.create_debater_agent", lambda *a, **k: MagicMock())
    monkeypatch.setattr("app.engine.debate.create_judge_agent", lambda *a, **k: MagicMock())
    monkeypatch.setattr("app.engine.debate.create_extractor_agent", lambda *a, **k: MagicMock())

    fresh_app = create_app()
    with TestClient(fresh_app) as client:
        # Inside the `with` block, lifespan startup has run.
        assert fresh_app.state.engine is not None
        assert isinstance(fresh_app.state.engine, DebateEngine)
        assert fresh_app.state.debater_repository is not None
        assert fresh_app.state.index_html

        # /api/presets continues to work via this fresh app.
        resp = client.get("/api/presets")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# app/agents.py: _make_model
# ---------------------------------------------------------------------------


def test_make_model_constructs_openai_chat_model():
    """``_make_model`` returns the post-rename ``OpenAIChatModel`` class.

    The legacy ``OpenAIModel`` alias was deprecated in pydantic-ai 1.7x and
    removed thereafter; ``OpenAIChatModel`` is the correct class for any
    OpenAI-compatible Chat Completions endpoint (DeepSeek, Ollama, vLLM, etc.).
    """
    from pydantic_ai.models.openai import OpenAIChatModel

    from app.agents import _make_model

    model = _make_model("gpt-test", base_url="https://api.example.com", api_key="k")
    assert isinstance(model, OpenAIChatModel)


# ---------------------------------------------------------------------------
# app/deps.py: DebaterRepository helpers + providers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debater_repository_list_custom_excludes_presets():
    repo = DebaterRepository()
    assert repo.list_custom() == []
    custom = Debater(name="新人", personality="x")
    assert await repo.add(custom) is True
    assert [d.name for d in repo.list_custom()] == ["新人"]
    # list_all() still includes presets, but list_custom() does not.
    assert any(d.name == "正方" for d in repo.list_all())
    assert not any(d.name == "正方" for d in repo.list_custom())


@pytest.mark.asyncio
async def test_debater_repository_find():
    repo = DebaterRepository()
    assert repo.find("does-not-exist") is None
    # Preset lookup works.
    assert repo.find("正方") is not None
    # Custom debater lookup works.
    custom = Debater(name="新人", personality="x")
    await repo.add(custom)
    assert repo.find("新人") is not None
    assert repo.find("新人").name == "新人"


def test_get_settings_returns_global_instance():
    from app.config import settings as global_settings

    assert get_settings() is global_settings


def test_get_engine_returns_engine_when_set():
    """When state.engine is set, get_engine returns it directly."""
    request = MagicMock()
    fake_engine = MagicMock(spec=DebateEngine)
    request.app.state.engine = fake_engine
    assert get_engine(request) is fake_engine


def test_get_engine_raises_when_unset():
    request = MagicMock()
    request.app.state.engine = None
    with pytest.raises(HTTPException) as exc_info:
        get_engine(request)
    assert exc_info.value.status_code == 503


def test_get_debater_repository_raises_when_unset():
    """Repository dep shares the same 503 readiness contract as the engine."""
    request = MagicMock()
    # Simulate lifespan not having run.
    del request.app.state.debater_repository
    with pytest.raises(HTTPException) as exc_info:
        get_debater_repository(request)
    assert exc_info.value.status_code == 503


def test_get_debater_repository_returns_state_repo():
    request = MagicMock()
    repo = DebaterRepository()
    request.app.state.debater_repository = repo
    assert get_debater_repository(request) is repo


# ---------------------------------------------------------------------------
# app/models.py: Debater.validate_color raises
# ---------------------------------------------------------------------------


def test_debater_invalid_color_raises():
    with pytest.raises(ValidationError) as exc_info:
        Debater(name="X", personality="p", color="not-a-color")
    assert "color must be a 6-digit hex color" in str(exc_info.value)


def test_debater_valid_color_accepted():
    d = Debater(name="X", personality="p", color="#abcdef")
    assert d.color == "#abcdef"


# ---------------------------------------------------------------------------
# app/engine/debate.py: __init__ wiring + ensure_loop_running + start cancel
# ---------------------------------------------------------------------------


def test_debate_engine_init_wires_agents(monkeypatch):
    """DebateEngine.__init__ should call all three agent factories."""
    debater = MagicMock(name="debater_agent")
    judge = MagicMock(name="judge_agent")
    extractor = MagicMock(name="extractor_agent")

    def fake_debater(*a, enable_search=True, **k):
        return debater

    monkeypatch.setattr("app.engine.debate.create_debater_agent", fake_debater)
    monkeypatch.setattr("app.engine.debate.create_judge_agent", lambda *a, **k: judge)
    monkeypatch.setattr("app.engine.debate.create_extractor_agent", lambda *a, **k: extractor)

    eng = DebateEngine(
        model="m",
        brave_api_key="bk",
        base_url="https://api.example.com",
        api_key="k",
    )
    assert eng.model == "m"
    assert eng.base_url == "https://api.example.com"
    assert eng.api_key == "k"
    assert eng.brave_api_key == "bk"
    assert eng.debater_agent is debater
    assert eng.debater_agent_no_search is debater
    assert eng.judge_agent is judge
    assert eng._extractor_agent is extractor
    assert eng.state is None
    assert eng._loop_task is None
    assert eng._history == {}


@pytest.mark.asyncio
async def test_start_cancels_existing_loop_task(monkeypatch):
    """A new start() should cancel any running loop task to avoid ghost tasks."""
    monkeypatch.setattr("app.engine.debate.create_debater_agent", lambda *a, **k: MagicMock())
    monkeypatch.setattr("app.engine.debate.create_judge_agent", lambda *a, **k: MagicMock())
    monkeypatch.setattr("app.engine.debate.create_extractor_agent", lambda *a, **k: MagicMock())

    eng = DebateEngine(model="m")

    async def _long_running():
        await asyncio.sleep(60)

    eng._loop_task = asyncio.create_task(_long_running())
    debater = Debater(name="x", personality="p")
    eng.start("topic", [debater])
    assert eng._loop_task is None or eng._loop_task.cancelled()
    # Give the cancellation a chance to settle for cleanliness.
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_ensure_loop_running_creates_task():
    """When state is active and no task exists, ensure_loop_running schedules one."""
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)

    async def fake_run_loop():
        pass

    eng.run_loop = fake_run_loop  # type: ignore[assignment]

    eng.ensure_loop_running()
    assert eng._loop_task is not None
    await eng._loop_task
    # Cleanup happens in _run_loop_and_cleanup
    assert eng._loop_task is None


def test_ensure_loop_running_noop_when_inactive():
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=False)
    eng.ensure_loop_running()
    assert eng._loop_task is None


def test_ensure_loop_running_noop_when_no_state():
    eng = _bare_engine()
    eng.state = None
    eng.ensure_loop_running()
    assert eng._loop_task is None


# ---------------------------------------------------------------------------
# app/engine/debate.py: tool-call streaming branches + initial TextPart content
# ---------------------------------------------------------------------------


def _make_engine_for_stream(stream_events_factory):
    """Helper: build an engine whose debater_agent yields the given events."""

    class _Agent:
        def __init__(self):
            self.last_kwargs = None

        def run_stream_events(self, *_args, **kwargs):
            self.last_kwargs = kwargs
            return _AsyncIter(stream_events_factory())

    class _AsyncIter:
        def __init__(self, events):
            self._events = list(events)

        async def __aiter__(self):
            for e in self._events:
                yield e

    agent = _Agent()
    eng = _bare_engine()
    eng.brave_api_key = "bk"
    eng.debater_agent = agent
    eng.debater_agent_no_search = agent
    eng._extractor_agent = MockDebateAgent(responses=['{"points": []}'])
    return eng, agent


def _make_function_tool_call_event(args):
    """Build a FunctionToolCallEvent whose .part.args is ``args``."""
    part = MagicMock(spec=ToolCallPart)
    part.args = args
    part.tool_name = "web_search"
    part.tool_call_id = "tc-1"
    return FunctionToolCallEvent(part=part)


def _make_function_tool_result_event(content: str | None):
    """Build a FunctionToolResultEvent whose .result.content is ``content``."""
    event = MagicMock(spec=FunctionToolResultEvent)
    event.__class__ = FunctionToolResultEvent
    result = MagicMock()
    result.content = content
    event.result = result
    event.tool_call_id = "tc-1"
    return event


@pytest.mark.asyncio
async def test_run_turn_tool_call_json_string_args():
    """FunctionToolCallEvent with JSON-string args is parsed and emits debater_finalize."""
    final_result = MagicMock()
    final_result.all_messages.return_value = []

    def events():
        return [
            _make_function_tool_call_event('{"query": "renewable energy 2026"}'),
            _make_function_tool_result_event("snippet of result content"),
            PartDeltaEvent(
                index=0,
                delta=__import__("pydantic_ai.messages", fromlist=["TextPartDelta"]).TextPartDelta(
                    content_delta="final argument"
                ),
            ),
            AgentRunResultEvent(result=final_result),
        ]

    eng, _ = _make_engine_for_stream(events)
    debater = Debater(name="Searcher", personality="p", enable_search=True)
    eng.state = DebateState(topic="T", debaters=[debater])
    eng._history = {"Searcher": []}

    await eng.run_turn()

    collected: list[Event] = []
    while not eng.event_queue.empty():
        collected.append(await eng.event_queue.get())
    types = [e.type for e in collected]
    assert "debater_finalize" in types  # emitted after tool call
    tool_events = [e for e in collected if e.type == "tool_call"]
    assert len(tool_events) == 1
    assert tool_events[0].payload["query"] == "renewable energy 2026"
    assert "snippet of result content" in tool_events[0].payload["result_summary"]


@pytest.mark.asyncio
async def test_run_turn_tool_call_malformed_json_args():
    """Malformed JSON args become empty dict — query defaults to ''."""
    final_result = MagicMock()
    final_result.all_messages.return_value = []

    def events():
        return [
            _make_function_tool_call_event("not-valid-json{{"),
            _make_function_tool_result_event(None),  # also covers empty-content branch
            AgentRunResultEvent(result=final_result),
        ]

    eng, _ = _make_engine_for_stream(events)
    debater = Debater(name="Searcher", personality="p", enable_search=True)
    eng.state = DebateState(topic="T", debaters=[debater])
    eng._history = {"Searcher": []}

    await eng.run_turn()

    collected: list[Event] = []
    while not eng.event_queue.empty():
        collected.append(await eng.event_queue.get())
    tool_events = [e for e in collected if e.type == "tool_call"]
    assert len(tool_events) == 1
    assert tool_events[0].payload["query"] == ""
    assert tool_events[0].payload["result_summary"] == ""


@pytest.mark.asyncio
async def test_run_turn_tool_call_dict_args():
    """When args are already a dict, no JSON parsing happens — query is read directly."""
    final_result = MagicMock()
    final_result.all_messages.return_value = []

    def events():
        return [
            _make_function_tool_call_event({"query": "已是字典"}),
            _make_function_tool_result_event("x" * 500),  # exercise the 200-char truncation
            AgentRunResultEvent(result=final_result),
        ]

    eng, _ = _make_engine_for_stream(events)
    debater = Debater(name="Searcher", personality="p", enable_search=True)
    eng.state = DebateState(topic="T", debaters=[debater])
    eng._history = {"Searcher": []}

    await eng.run_turn()

    collected: list[Event] = []
    while not eng.event_queue.empty():
        collected.append(await eng.event_queue.get())
    tool_events = [e for e in collected if e.type == "tool_call"]
    assert tool_events[0].payload["query"] == "已是字典"
    assert len(tool_events[0].payload["result_summary"]) == 200


@pytest.mark.asyncio
async def test_run_turn_initial_text_part_content():
    """PartStartEvent with non-empty TextPart.content emits debater_chunk and accumulates."""
    final_result = MagicMock()
    final_result.all_messages.return_value = []

    def events():
        return [
            PartStartEvent(index=0, part=TextPart(content="opening words")),
            AgentRunResultEvent(result=final_result),
        ]

    eng, _ = _make_engine_for_stream(events)
    debater = Debater(name="Alice", personality="p", enable_search=False)
    eng.state = DebateState(topic="T", debaters=[debater])
    eng._history = {"Alice": []}

    await eng.run_turn()

    collected: list[Event] = []
    while not eng.event_queue.empty():
        collected.append(await eng.event_queue.get())
    chunks = [e for e in collected if e.type == "debater_chunk"]
    assert chunks
    assert chunks[0].payload["text_chunk"] == "opening words"
    end_event = next(e for e in collected if e.type == "debater_end")
    assert "opening words" in end_event.payload["full_text"]


@pytest.mark.asyncio
async def test_run_turn_text_part_after_thinking_emits_finalize():
    """A non-empty initial TextPart after thinking should also finalize the thinking section."""
    final_result = MagicMock()
    final_result.all_messages.return_value = []

    def events():
        return [
            PartStartEvent(index=0, part=ThinkingPart(content="hmm let me think")),
            PartStartEvent(index=1, part=TextPart(content="my answer")),
            AgentRunResultEvent(result=final_result),
        ]

    eng, _ = _make_engine_for_stream(events)
    debater = Debater(name="Alice", personality="p", enable_search=False)
    eng.state = DebateState(topic="T", debaters=[debater])
    eng._history = {"Alice": []}

    await eng.run_turn()

    collected: list[Event] = []
    while not eng.event_queue.empty():
        collected.append(await eng.event_queue.get())
    types = [e.type for e in collected]
    # finalize must appear between thinking_chunk and the debater_chunk for text.
    thinking_idx = types.index("thinking_chunk")
    finalize_idx = types.index("debater_finalize")
    chunk_idx = types.index("debater_chunk")
    assert thinking_idx < finalize_idx < chunk_idx


# ---------------------------------------------------------------------------
# app/engine/debate.py: extract_key_points empty text + judge transcript
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_key_points_empty_text_short_circuits():
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")])
    eng._extractor_agent = MockDebateAgent(responses=['{"points": ["should not be called"]}'])

    await eng._extract_key_points("x", "   ", 0)

    # The early return means the extractor was never invoked.
    assert eng._extractor_agent.call_count == 0
    assert eng.state.argument_summaries == []


@pytest.mark.asyncio
async def test_judge_transcript_includes_history():
    """judge() builds a transcript that includes all history messages."""
    eng = _bare_engine()
    eng.state = DebateState(
        topic="t",
        debaters=[Debater(name="A", personality="p")],
        history=[
            __import__("app.engine.state", fromlist=["Message"]).Message(
                speaker="A", content="hello"
            ),
            __import__("app.engine.state", fromlist=["Message"]).Message(
                speaker="B", content="reply"
            ),
        ],
    )
    judge_mock = MockDebateAgent(responses=["my judgment"])
    eng.judge_agent = judge_mock

    result = await eng.judge()
    assert result is True
    assert judge_mock.last_user_prompt is not None
    assert "[A]: hello" in judge_mock.last_user_prompt
    assert "[B]: reply" in judge_mock.last_user_prompt

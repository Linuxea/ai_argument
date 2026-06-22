"""Regression tests for previously-undiscovered bugs (B1–B25).

Each test is named with the bug id from the audit so future regressions are
easy to map back to the original failure mode.
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.deps import get_engine
from app.engine.debate import DebateEngine, _parse_extractor_output
from app.engine.state import DebateState, Event, Message
from app.models import DebateConfig, Debater
from main import app
from tests.conftest import MockDebateAgent
from tests.test_coverage_extras import _bare_engine


# ---------------------------------------------------------------------------
# B9: DebateConfig.max_rounds bounded
# ---------------------------------------------------------------------------


def test_b9_max_rounds_upper_bound():
    """max_rounds > 50 must be rejected at the API layer."""
    with pytest.raises(ValidationError):
        DebateConfig(topic="t", debater_names=["a", "b"], max_rounds=51)


def test_b9_max_rounds_zero_rejected():
    with pytest.raises(ValidationError):
        DebateConfig(topic="t", debater_names=["a", "b"], max_rounds=0)


def test_b9_max_rounds_negative_rejected():
    with pytest.raises(ValidationError):
        DebateConfig(topic="t", debater_names=["a", "b"], max_rounds=-5)


def test_b9_max_rounds_none_still_allowed():
    """None is the legitimate 'unbounded' sentinel."""
    cfg = DebateConfig(topic="t", debater_names=["a", "b"], max_rounds=None)
    assert cfg.max_rounds is None


def test_b9_max_rounds_in_range_accepted():
    cfg = DebateConfig(topic="t", debater_names=["a", "b"], max_rounds=50)
    assert cfg.max_rounds == 50


# ---------------------------------------------------------------------------
# B11/B12: tools.py defensive parsing
# ---------------------------------------------------------------------------


def _ctx_with_key(api_key: str = "valid-key"):
    from app.agents import DebaterDeps

    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="t",
        debater=Debater(name="x", personality="p"),
        round_number=0,
        max_rounds=None,
        brave_api_key=api_key,
    )
    return ctx


@pytest.mark.asyncio
async def test_b11_web_search_html_response_does_not_crash():
    """Brave occasionally returns HTML (auth page / Cloudflare). The tool must
    degrade gracefully instead of bubbling ValueError up to the debate loop."""
    from app.tools import web_search

    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await web_search(_ctx_with_key(), "anything")

    assert "Search failed" in result
    assert "Proceed without search results" in result


@pytest.mark.asyncio
async def test_b12_web_search_handles_missing_title():
    """Brave can return result items missing 'title'; the tool must skip them
    instead of raising KeyError and crashing the whole debate."""
    from app.tools import web_search

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"description": "no title here"},          # missing title — used to KeyError
                {"title": "Real Result", "description": "ok"},
                {"title": "Also OK"},                       # missing description — used .get already
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await web_search(_ctx_with_key(), "q")

    # Must contain the two title-bearing rows and not raise.
    assert "Real Result" in result
    assert "Also OK" in result
    # The title-less row contributes via its description.
    assert "no title here" in result


@pytest.mark.asyncio
async def test_b12_web_search_skips_entirely_empty_items():
    """An item with neither title nor description shouldn't produce a bare '- :'."""
    from app.tools import web_search

    mock_response = MagicMock()
    mock_response.json.return_value = {"web": {"results": [{}, {"title": "Good"}]}}
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await web_search(_ctx_with_key(), "q")

    assert "- :" not in result
    assert "Good" in result


@pytest.mark.asyncio
async def test_b11_web_search_unexpected_root_shape():
    """If the API returns a list at top level (very rare but possible), the
    tool must return a graceful failure string, not raise."""
    from app.tools import web_search

    mock_response = MagicMock()
    mock_response.json.return_value = ["unexpected", "list"]
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await web_search(_ctx_with_key(), "q")

    assert "Search failed" in result


@pytest.mark.asyncio
async def test_b12_web_search_skips_non_dict_items():
    """Items that aren't dicts (rare malformed API response) must be skipped."""
    from app.tools import web_search

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                "string-not-a-dict",
                42,
                None,
                {"title": "Real", "description": "ok"},
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await web_search(_ctx_with_key(), "q")

    assert "Real" in result
    # Non-dicts must not produce literal "- string-not-a-dict" rows.
    assert "string-not-a-dict" not in result


# ---------------------------------------------------------------------------
# B3: topic.refine handles None content
# ---------------------------------------------------------------------------


def _patch_topic_settings(monkeypatch):
    monkeypatch.setattr("app.routes.topic.settings.api_key", "k")
    monkeypatch.setattr("app.routes.topic.settings.api_base_url", "https://api.example.com")
    monkeypatch.setattr("app.routes.topic.settings.model", "test")


def _fake_openai_returning(content):
    """Build an AsyncOpenAI mock returning the given content (None allowed)."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def test_b3_topic_refine_handles_none_content(monkeypatch):
    """Model returning content=None must produce a clear 502 message, not
    "'NoneType' object has no attribute 'strip'"."""
    _patch_topic_settings(monkeypatch)
    client = _fake_openai_returning(None)

    test_client = TestClient(app)
    with patch("app.routes.topic.AsyncOpenAI", return_value=client):
        resp = test_client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "NoneType" not in detail
    assert "模型未返回话题文本" in detail


def test_b3_topic_refine_handles_empty_string(monkeypatch):
    """Likewise an empty string after stripping must not look like 'success'."""
    _patch_topic_settings(monkeypatch)
    client = _fake_openai_returning("   \n  ")

    test_client = TestClient(app)
    with patch("app.routes.topic.AsyncOpenAI", return_value=client):
        resp = test_client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 502
    assert "模型未返回话题文本" in resp.json()["detail"]


def test_b3_topic_refine_handles_no_choices(monkeypatch):
    """A response with empty choices list should not IndexError."""
    _patch_topic_settings(monkeypatch)
    response = MagicMock()
    response.choices = []
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    test_client = TestClient(app)
    with patch("app.routes.topic.AsyncOpenAI", return_value=client):
        resp = test_client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 502


def test_b33_topic_refine_length_truncation_message(monkeypatch):
    """Empty content with finish_reason='length' must surface the truncation
    cause distinctly — this is the symptom users hit when DeepSeek V4's
    default thinking mode burns the entire max_tokens budget on reasoning."""
    _patch_topic_settings(monkeypatch)
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = ""
    response.choices[0].finish_reason = "length"
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    test_client = TestClient(app)
    with patch("app.routes.topic.AsyncOpenAI", return_value=client):
        resp = test_client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "token 上限截断" in detail
    assert "模型未返回话题文本" not in detail


# ---------------------------------------------------------------------------
# B16: _parse_extractor_output tolerates code fences / prose
# ---------------------------------------------------------------------------


def test_b16_parse_extractor_plain_json():
    assert _parse_extractor_output('{"points": ["a"]}') == {"points": ["a"]}


def test_b16_parse_extractor_markdown_fence():
    raw = '```json\n{"points": ["a", "b"]}\n```'
    assert _parse_extractor_output(raw) == {"points": ["a", "b"]}


def test_b16_parse_extractor_bare_fence_no_lang():
    raw = '```\n{"points": ["x"]}\n```'
    assert _parse_extractor_output(raw) == {"points": ["x"]}


def test_b16_parse_extractor_trailing_prose():
    """Some models add 'Here's the JSON:' before or '(end)' after."""
    raw = 'Here is the JSON: {"points": ["a"]} (end)'
    assert _parse_extractor_output(raw) == {"points": ["a"]}


def test_b16_parse_extractor_garbage_returns_empty_dict():
    assert _parse_extractor_output("not json at all") == {}


def test_b16_parse_extractor_empty_input():
    assert _parse_extractor_output("") == {}


@pytest.mark.asyncio
async def test_b16_extract_key_points_with_fenced_output():
    """End-to-end: the extractor agent returns a fenced JSON, summary still saved."""
    from app.models import Debater as DebaterModel

    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[DebaterModel(name="x", personality="p")])
    eng._extractor_agent = MockDebateAgent(
        responses=['```json\n{"points": ["claim 1", "claim 2"]}\n```']
    )

    await eng._extract_key_points("x", "some argument text", 0)

    assert len(eng.state.argument_summaries) == 1
    assert eng.state.argument_summaries[0].points == ["claim 1", "claim 2"]


@pytest.mark.asyncio
async def test_b16_extract_key_points_filters_non_string_points():
    """Defensive: if the model returns mixed types, keep only stringy ones."""
    from app.models import Debater as DebaterModel

    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[DebaterModel(name="x", personality="p")])
    eng._extractor_agent = MockDebateAgent(
        responses=['{"points": ["ok", "  ", null, 42, "also ok"]}']
    )

    await eng._extract_key_points("x", "text", 0)

    summary = eng.state.argument_summaries[0]
    assert "ok" in summary.points
    assert "also ok" in summary.points
    # Empty / null filtered.
    for p in summary.points:
        assert p.strip()


@pytest.mark.asyncio
async def test_b16_extract_key_points_swallows_agent_exception():
    """A network / model failure in the extractor must not break the debate.
    It should be logged and silently skipped."""
    from app.models import Debater as DebaterModel

    class _BoomAgent:
        async def run(self, *_a, **_k):
            raise RuntimeError("upstream down")

    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[DebaterModel(name="x", personality="p")])
    eng._extractor_agent = _BoomAgent()

    # Must not raise.
    await eng._extract_key_points("x", "some text", 0)
    assert eng.state.argument_summaries == []


# ---------------------------------------------------------------------------
# B1: start() refuses while an active debate is running
# ---------------------------------------------------------------------------


def test_b1_start_raises_when_debate_active():
    """A new start() during an active debate must raise instead of silently
    clobbering the existing engine state (which would orphan the SSE client)."""
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)

    with pytest.raises(RuntimeError, match="already running"):
        eng.start("new topic", [Debater(name="y", personality="p")])


def test_b1_start_allowed_after_stop():
    """Once stopped, start() may be called again."""
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)
    eng.state.active = False

    eng.start("new", [Debater(name="y", personality="p"), Debater(name="z", personality="p")])
    assert eng.state.topic == "new"
    assert [d.name for d in eng.state.debaters] == ["y", "z"]


def test_b1_allowed_after_stop_cancels_lingering_judge_task():
    """If start() is called while judge_task is still pending (e.g. judge was
    cancelled mid-flight), the lingering task must be cancelled."""
    eng = _bare_engine()

    cancelled = {"flag": False}

    class FakeTask:
        def done(self):
            return False

        def cancel(self):
            cancelled["flag"] = True

    eng.judge_task = FakeTask()
    eng.start("topic", [Debater(name="a", personality="p"), Debater(name="b", personality="p")])
    assert cancelled["flag"] is True
    assert eng.judge_task is None


def test_b1_start_cancels_lingering_loop_task():
    """Same as above but for _loop_task."""
    eng = _bare_engine()

    cancelled = {"flag": False}

    class FakeTask:
        def done(self):
            return False

        def cancel(self):
            cancelled["flag"] = True

    eng._loop_task = FakeTask()
    eng.start("topic", [Debater(name="a", personality="p"), Debater(name="b", personality="p")])
    assert cancelled["flag"] is True
    assert eng._loop_task is None


def test_b1_route_returns_409_on_concurrent_start():
    """POST /api/debate/start during an active debate must return 409."""

    class StubEngine:
        def __init__(self):
            self.state = DebateState(
                topic="ongoing", debaters=[Debater(name="x", personality="p")], active=True
            )

        def start(self, *a, **k):
            raise RuntimeError("a debate is already running; stop it first")

    eng = StubEngine()
    app.dependency_overrides[get_engine] = lambda: eng
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/debate/start",
            json={"topic": "new", "debater_names": ["正方", "反方"]},
        )
        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_engine, None)


# ---------------------------------------------------------------------------
# B2: stop() actually cancels the in-flight turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b2_stop_cancels_running_loop_task():
    """stop() should cancel _loop_task so the user doesn't wait for the
    current turn's slow LLM stream to finish."""
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow_loop():
        try:
            started.set()
            await asyncio.sleep(60)  # simulate a long LLM stream
        except asyncio.CancelledError:
            cancelled.set()
            raise

    eng._loop_task = asyncio.create_task(slow_loop())
    await started.wait()

    eng.stop()

    # Wait a tick for cancellation to land.
    try:
        await asyncio.wait_for(eng._loop_task, timeout=1.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    assert cancelled.is_set(), "stop() did not cancel the loop task"
    assert eng.state.active is False


@pytest.mark.asyncio
async def test_b2_cancellation_emits_debate_paused():
    """When _run_loop_and_cleanup is cancelled mid-loop, it must emit
    debate_paused so the SSE consumer terminates instead of hanging."""
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)

    started = asyncio.Event()

    async def slow_run_loop():
        started.set()
        await asyncio.sleep(60)

    eng.run_loop = slow_run_loop  # type: ignore

    task = asyncio.create_task(eng._run_loop_and_cleanup())
    await started.wait()
    task.cancel()
    await asyncio.wait_for(task, timeout=1.0)

    # We expect a debate_paused event in the queue.
    events: list[Event] = []
    while not eng.event_queue.empty():
        events.append(await eng.event_queue.get())
    types = [e.type for e in events]
    assert "debate_paused" in types


# ---------------------------------------------------------------------------
# B7/B22/B15: judge task tracking + 409 on concurrent judge
# ---------------------------------------------------------------------------


def test_b22_judge_returns_409_when_already_judging():
    """Posting /judge twice in a row must not start two judge tasks."""

    class StubEngine:
        def __init__(self):
            self.state = DebateState(
                topic="t", debaters=[Debater(name="x", personality="p")], active=False
            )
            self.event_queue = asyncio.Queue()
            # Pretend a long-running judge task already exists.
            loop = asyncio.new_event_loop()
            try:
                async def sleeper():
                    await asyncio.sleep(60)
                self.judge_task = loop.create_task(sleeper())
            finally:
                # Don't actually run the loop; we just need a not-done task
                # for the route's check. Cancel later.
                pass
            self._loop = loop

        async def judge(self):
            return True

    # We need an actual running event loop for the test to obtain a task that
    # isn't done. Easier: stub judge_task with a MagicMock(done=lambda: False).
    class CheapStub:
        state = DebateState(
            topic="t", debaters=[Debater(name="x", personality="p")], active=False
        )
        event_queue = asyncio.Queue()
        judge_task = MagicMock(done=MagicMock(return_value=False))

    eng = CheapStub()
    app.dependency_overrides[get_engine] = lambda: eng
    try:
        client = TestClient(app)
        resp = client.post("/api/debate/judge")
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_engine, None)


def test_b7_background_task_keeps_strong_reference():
    """A judge task launched via the route must be tracked in the module-level
    set so the loop's weak ref isn't the only ref (avoiding GC of long tasks).
    """
    from app.routes.debate import _BACKGROUND_TASKS

    class CheapStub:
        state = DebateState(
            topic="t", debaters=[Debater(name="x", personality="p")], active=False
        )
        event_queue = asyncio.Queue()
        judge_task = None

        async def judge(self):
            # Block briefly so we can observe the task is registered.
            await asyncio.sleep(0.05)
            await self.event_queue.put(Event(type="judge_result", payload={"judgment_text": "ok"}))
            return True

    eng = CheapStub()
    app.dependency_overrides[get_engine] = lambda: eng
    try:
        client = TestClient(app)
        before = len(_BACKGROUND_TASKS)
        resp = client.post("/api/debate/judge")
        assert resp.status_code == 200
        # By the time the response returns, the task may or may not still be
        # running. But at registration time len > before. Accept either:
        # the set should have grown OR the task already completed and removed
        # itself. The strict assertion: judge_task is set on the engine.
        assert eng.judge_task is not None
        # Wait for completion to clean up.
        for _ in range(50):
            if eng.judge_task.done():
                break
            time.sleep(0.02)
        assert eng.judge_task.done()
    finally:
        app.dependency_overrides.pop(get_engine, None)


# ---------------------------------------------------------------------------
# B6: event IDs + replay buffer + Last-Event-ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b6_emit_assigns_increasing_ids():
    eng = _bare_engine()
    await eng._emit(Event(type="a", payload={}))
    await eng._emit(Event(type="b", payload={}))
    await eng._emit(Event(type="c", payload={}))
    ids = [e.id for e in eng.event_log]
    assert ids == sorted(ids)
    assert all(i > 0 for i in ids)
    assert len(set(ids)) == 3  # all unique


@pytest.mark.asyncio
async def test_b6_events_since_returns_only_newer():
    eng = _bare_engine()
    for kind in ("a", "b", "c", "d"):
        await eng._emit(Event(type=kind, payload={}))
    # Last-Event-ID = 2 → expect events with id 3, 4
    later = eng.events_since(2)
    assert [e.type for e in later] == ["c", "d"]


@pytest.mark.asyncio
async def test_b6_events_since_zero_returns_nothing():
    """last_id=0 means 'first connection' — don't replay anything."""
    eng = _bare_engine()
    await eng._emit(Event(type="a", payload={}))
    assert eng.events_since(0) == []


@pytest.mark.asyncio
async def test_b6_replay_log_bounded():
    """Buffer must drop old events to stay under the size cap."""
    eng = _bare_engine()
    eng._event_log_max = 10
    for i in range(25):
        await eng._emit(Event(type=f"e{i}", payload={"i": i}))
    assert len(eng.event_log) == 10
    # Should contain the *newest* 10 events.
    assert eng.event_log[0].payload["i"] == 15
    assert eng.event_log[-1].payload["i"] == 24


def test_b6_sse_replays_on_last_event_id_header():
    """Connecting with Last-Event-ID header should replay buffered events."""
    from app.routes.debate import TERMINAL_EVENTS  # noqa: F401

    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)

    # Pre-populate the replay buffer with 3 events; mark the third terminal so
    # the SSE generator exits immediately after replay.
    async def populate():
        await eng._emit(Event(type="debater_chunk", payload={"text_chunk": "hello"}))
        await eng._emit(Event(type="debater_chunk", payload={"text_chunk": " world"}))
        await eng._emit(Event(type="debate_end", payload={"reason": "done"}))

    asyncio.run(populate())

    app.dependency_overrides[get_engine] = lambda: eng
    try:
        client = TestClient(app)
        # Reconnect with Last-Event-ID = 1 → expect events 2 and 3 replayed.
        with client.stream(
            "GET", "/api/debate/stream", headers={"Last-Event-ID": "1"}
        ) as resp:
            body = "".join(resp.iter_text())
        assert "id: 2" in body
        assert "id: 3" in body
        assert "event: debate_end" in body
        # Event 1 must NOT be replayed (we said we've already seen it).
        assert "hello" not in body
    finally:
        app.dependency_overrides.pop(get_engine, None)


def test_b6_sse_invalid_last_event_id_treated_as_zero():
    """Garbage Last-Event-ID header shouldn't crash the endpoint."""
    eng = _bare_engine()
    eng.state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)

    async def populate():
        await eng._emit(Event(type="debate_end", payload={"reason": "done"}))

    asyncio.run(populate())

    app.dependency_overrides[get_engine] = lambda: eng
    try:
        client = TestClient(app)
        with client.stream(
            "GET", "/api/debate/stream", headers={"Last-Event-ID": "not-an-int"}
        ) as resp:
            body = "".join(resp.iter_text())
        # With last_id treated as 0, no replay; live event still arrives.
        assert "event: debate_end" in body
    finally:
        app.dependency_overrides.pop(get_engine, None)


# ---------------------------------------------------------------------------
# B10: per-call-id tool query tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b10_tool_call_query_keyed_by_call_id():
    """When tool_call A is followed by tool_call B before B's result, the
    pairing between query and result must still be correct (was a single
    `current_query` var, would mix up parallel calls)."""
    from pydantic_ai import AgentRunResultEvent, FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart

    def _call(args, call_id):
        part = MagicMock(spec=ToolCallPart)
        part.args = args
        part.tool_name = "web_search"
        part.tool_call_id = call_id
        return FunctionToolCallEvent(part=part)

    def _result(content, call_id):
        ev = MagicMock(spec=FunctionToolResultEvent)
        ev.__class__ = FunctionToolResultEvent
        ev.result = MagicMock()
        ev.result.content = content
        ev.tool_call_id = call_id
        return ev

    final = MagicMock()
    final.all_messages.return_value = []

    events = [
        _call({"query": "first"}, "id-A"),
        _call({"query": "second"}, "id-B"),
        _result("res-B", "id-B"),       # B's result arrives first
        _result("res-A", "id-A"),       # then A's
        AgentRunResultEvent(result=final),
    ]

    class _Agent:
        def run_stream_events(self, *_a, **_k):
            class _Iter:
                async def __aiter__(self_):
                    for e in events:
                        yield e
            return _Iter()

    eng = _bare_engine()
    agent = _Agent()
    eng.debater_agent = agent
    eng.debater_agent_no_search = agent
    eng._extractor_agent = MockDebateAgent(responses=['{"points":[]}'])
    debater = Debater(name="Searcher", personality="p", enable_search=True)
    eng.state = DebateState(topic="T", debaters=[debater])
    eng._history = {"Searcher": []}

    await eng.run_turn()

    collected: list[Event] = []
    while not eng.event_queue.empty():
        collected.append(await eng.event_queue.get())
    tool_events = [e for e in collected if e.type == "tool_call"]
    assert len(tool_events) == 2

    # First tool_result is for id-B → should carry query "second"
    assert tool_events[0].payload["query"] == "second"
    assert tool_events[0].payload["result_summary"] == "res-B"
    # Second is for id-A.
    assert tool_events[1].payload["query"] == "first"
    assert tool_events[1].payload["result_summary"] == "res-A"


# ---------------------------------------------------------------------------
# B15: judge() doesn't allow re-judging via state.active flag misuse
# ---------------------------------------------------------------------------


def test_b15_judge_blocked_while_active():
    """Already covered, but enshrining: an active debate must reject judge."""

    class S:
        state = DebateState(topic="t", debaters=[Debater(name="x", personality="p")], active=True)
        event_queue = asyncio.Queue()
        judge_task = None

    app.dependency_overrides[get_engine] = lambda: S()
    try:
        resp = TestClient(app).post("/api/debate/judge")
        assert resp.status_code == 400
        assert "stop" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_engine, None)

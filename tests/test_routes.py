"""Integration tests for FastAPI route handlers (debate / debaters / topic)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.deps import DebaterRepository, get_debater_repository, get_engine
from app.engine.state import DebateState, Event
from app.models import Debater
from main import app

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeEngine:
    """Stand-in engine that records calls and exposes a writable event_queue."""

    def __init__(self) -> None:
        self.state: DebateState | None = None
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.judge_task: asyncio.Task | None = None
        self.start_called: tuple | None = None
        self.inject_called: str | None = None
        self.stop_called = False
        self.resume_called = False
        self.ensure_loop_called = False
        self.judge_called = False
        self.judge_raises: Exception | None = None

    def start(self, topic, debaters, max_rounds=None):
        self.start_called = (topic, list(debaters), max_rounds)
        self.state = DebateState(topic=topic, debaters=debaters, max_rounds=max_rounds)

    def stop(self):
        self.stop_called = True
        if self.state:
            self.state.active = False

    def resume(self):
        self.resume_called = True
        if self.state:
            self.state.active = True

    def inject_message(self, msg):
        self.inject_called = msg

    def ensure_loop_running(self):
        self.ensure_loop_called = True

    async def judge(self):
        self.judge_called = True
        if self.judge_raises:
            raise self.judge_raises
        await self.event_queue.put(Event(type="judge_result", payload={"judgment_text": "ok"}))
        return True

    async def emit_error(self, message: str, *, judge: bool = False) -> None:
        """Mirror the real engine's terminal-error helper."""
        event_type = "judge_error" if judge else "debate_error"
        await self.event_queue.put(Event(type=event_type, payload={"message": message}))

    # Single-consumer slot mirror. The real engine uses these to enforce that
    # only one /api/debate/stream pulls from event_queue at a time.
    def acquire_consumer(self) -> bool:
        if getattr(self, "_consumer_active", False):
            return False
        self._consumer_active = True
        return True

    def release_consumer(self) -> None:
        self._consumer_active = False


@pytest.fixture
def fake_engine():
    eng = FakeEngine()
    app.dependency_overrides[get_engine] = lambda: eng
    yield eng
    app.dependency_overrides.pop(get_engine, None)


@pytest.fixture
def fresh_repository():
    """Swap the repo for a clean one so custom-debater tests don't bleed state."""
    repo = DebaterRepository()
    app.dependency_overrides[get_debater_repository] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_debater_repository, None)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# /api/debate/start
# ---------------------------------------------------------------------------


def test_start_debate_success(fake_engine, client):
    resp = client.post(
        "/api/debate/start",
        json={"topic": "AI in education", "debater_names": ["正方", "反方"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "started", "topic": "AI in education"}
    assert fake_engine.start_called is not None
    topic, debaters, _ = fake_engine.start_called
    assert topic == "AI in education"
    assert [d.name for d in debaters] == ["正方", "反方"]


def test_start_debate_with_max_rounds(fake_engine, client):
    resp = client.post(
        "/api/debate/start",
        json={"topic": "T", "debater_names": ["正方", "反方"], "max_rounds": 3},
    )
    assert resp.status_code == 200
    assert fake_engine.start_called[2] == 3


def test_start_debate_min_debaters(fake_engine, client):
    resp = client.post(
        "/api/debate/start",
        json={"topic": "Test", "debater_names": ["正方"]},
    )
    # min_length=2 is a Pydantic field constraint → 422 Unprocessable Entity.
    assert resp.status_code == 422


def test_start_debate_rejects_duplicate_names(fake_engine, client):
    """Duplicate debater names are rejected at the model layer (C1)."""
    resp = client.post(
        "/api/debate/start",
        json={"topic": "Test", "debater_names": ["正方", "正方"]},
    )
    assert resp.status_code == 422


def test_start_debate_unknown_name(fake_engine, client):
    resp = client.post(
        "/api/debate/start",
        json={"topic": "Test", "debater_names": ["正方", "ghost-not-real"]},
    )
    assert resp.status_code == 400
    assert "Invalid debater" in resp.json()["detail"]


def test_start_debate_without_engine(client):
    """When engine isn't initialised, get_engine returns 503 (service not ready).

    Explicitly clears ``app.state.engine`` so the test is robust against
    sibling tests that ran lifespan via ``with TestClient(app):`` and left a
    real engine instance on shared app state.
    """
    app.dependency_overrides.pop(get_engine, None)
    saved_engine = app.state.engine
    app.state.engine = None
    try:
        resp = client.post(
            "/api/debate/start",
            json={"topic": "Test", "debater_names": ["正方", "反方"]},
        )
        assert resp.status_code == 503
        assert "not ready" in resp.json()["detail"].lower()
    finally:
        app.state.engine = saved_engine


# ---------------------------------------------------------------------------
# /api/debate/message
# ---------------------------------------------------------------------------


def test_inject_message_when_active(fake_engine, client):
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=True
    )
    resp = client.post("/api/debate/message", json={"message": "hello there"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "injected"}
    assert fake_engine.inject_called == "hello there"


def test_inject_message_when_no_state(fake_engine, client):
    resp = client.post("/api/debate/message", json={"message": "hi"})
    assert resp.status_code == 400


def test_inject_message_when_inactive(fake_engine, client):
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=False
    )
    resp = client.post("/api/debate/message", json={"message": "hi"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /api/debate/stop and /resume
# ---------------------------------------------------------------------------


def test_stop_with_state(fake_engine, client):
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=True
    )
    resp = client.post("/api/debate/stop")
    assert resp.status_code == 200
    assert resp.json() == {"status": "stopped"}
    assert fake_engine.stop_called


def test_stop_without_state(fake_engine, client):
    resp = client.post("/api/debate/stop")
    assert resp.status_code == 400


def test_resume_with_state(fake_engine, client):
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=False
    )
    resp = client.post("/api/debate/resume")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resumed"
    assert body["needs_sse_reconnect"] is True
    assert fake_engine.resume_called


def test_resume_without_state(fake_engine, client):
    resp = client.post("/api/debate/resume")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /api/debate/judge
# ---------------------------------------------------------------------------


def test_judge_without_state(fake_engine, client):
    resp = client.post("/api/debate/judge")
    assert resp.status_code == 400


def test_judge_while_active(fake_engine, client):
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=True
    )
    resp = client.post("/api/debate/judge")
    assert resp.status_code == 400
    assert "stop" in resp.json()["detail"].lower()


def test_judge_when_paused(fake_engine, client):
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=False
    )
    resp = client.post("/api/debate/judge")
    assert resp.status_code == 200
    assert resp.json() == {"status": "judging"}


@pytest.mark.asyncio
async def test_safe_judge_emits_judge_error_on_exception():
    """_safe_judge wraps judge() and emits a judge_error terminal event on failure.

    The error message must be generic (no provider detail leaked to clients).
    """
    from app.routes.debate import _safe_judge

    eng = FakeEngine()
    eng.judge_raises = RuntimeError("kaboom")
    await _safe_judge(eng)

    events: list[Event] = []
    while not eng.event_queue.empty():
        events.append(await eng.event_queue.get())
    error_events = [e for e in events if e.type == "judge_error"]
    assert len(error_events) == 1
    # Generic message; provider exception text MUST NOT leak.
    assert "kaboom" not in error_events[0].payload["message"]
    assert error_events[0].payload["message"]  # non-empty generic message


# ---------------------------------------------------------------------------
# /api/debate/stream
# ---------------------------------------------------------------------------


def test_stream_terminates_on_terminal_event(fake_engine, client):
    """SSE stream emits queued events and exits when a terminal event arrives."""
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=True
    )
    fake_engine.event_queue.put_nowait(
        Event(type="debater_chunk", payload={"debater_name": "x", "text_chunk": "hi"})
    )
    fake_engine.event_queue.put_nowait(Event(type="debate_end", payload={"reason": "done"}))

    with client.stream("GET", "/api/debate/stream") as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    assert "event: debater_chunk" in body
    assert "event: debate_end" in body
    assert fake_engine.ensure_loop_called
    # Consumer slot must be released on graceful exit so the next stream can
    # connect without a 409.
    assert fake_engine._consumer_active is False


def test_stream_rejects_second_consumer_with_409(fake_engine, client):
    """M5: a second concurrent /stream consumer returns 409 so events aren't
    split between two waiters on event_queue.get()."""
    fake_engine._consumer_active = True  # simulate an already-connected consumer

    resp = client.get("/api/debate/stream")
    assert resp.status_code == 409
    assert "already active" in resp.json()["detail"]


def test_stream_exits_immediately_when_no_state(fake_engine, client):
    """If engine.state is None, the generator falls through and closes."""
    # state stays None
    with client.stream("GET", "/api/debate/stream") as resp:
        body = "".join(resp.iter_text())
    assert resp.status_code == 200
    assert body == ""


def test_stream_emits_keepalive_on_timeout(fake_engine, client, monkeypatch):
    """When event_queue.get() times out, a keepalive comment is emitted."""
    fake_engine.state = DebateState(
        topic="t", debaters=[Debater(name="x", personality="x")], active=True
    )

    real_wait_for = asyncio.wait_for
    calls = {"n": 0}

    async def flaky_wait_for(coro, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            # Cancel the get coroutine so it's not left dangling, then raise.
            if asyncio.iscoroutine(coro):
                coro.close()
            raise asyncio.TimeoutError
        # Second call: deliver a terminal event so the stream finishes.
        return await real_wait_for(coro, timeout)

    fake_engine.event_queue.put_nowait(Event(type="debate_end", payload={"reason": "done"}))
    monkeypatch.setattr("app.routes.debate.asyncio.wait_for", flaky_wait_for)

    with client.stream("GET", "/api/debate/stream") as resp:
        body = "".join(resp.iter_text())

    assert ": keepalive" in body
    assert "event: debate_end" in body


# ---------------------------------------------------------------------------
# /api/debaters and /api/presets
# ---------------------------------------------------------------------------


def test_get_all_debaters_includes_presets(fresh_repository, client):
    resp = client.get("/api/debaters")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert "正方" in names
    assert "反方" in names
    assert "分析家" in names


def test_create_custom_debater(fresh_repository, client):
    payload = {
        "name": "实用主义者",
        "color": "#9b59b6",
        "avatar": "🟣",
        "stance": "中立",
        "personality": "你是实用主义者。",
        "enable_search": False,
    }
    resp = client.post("/api/debaters", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "created"
    assert body["debater"]["name"] == "实用主义者"

    # Verify it appears in the listing now.
    resp2 = client.get("/api/debaters")
    names = [d["name"] for d in resp2.json()]
    assert "实用主义者" in names


def test_create_custom_debater_duplicate(fresh_repository, client):
    payload = {
        "name": "唯一主义者",
        "color": "#9b59b6",
        "avatar": "🟣",
        "stance": "中立",
        "personality": "...",
    }
    resp1 = client.post("/api/debaters", json=payload)
    assert resp1.status_code == 200
    resp2 = client.post("/api/debaters", json=payload)
    assert resp2.status_code == 409


def test_create_custom_debater_duplicates_preset_name(fresh_repository, client):
    """Preset names should also be rejected for new custom debaters."""
    payload = {"name": "正方", "personality": "..."}
    resp = client.post("/api/debaters", json=payload)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# /api/topic/refine
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_settings_with_key(monkeypatch):
    """Make the topic refiner believe an API key is configured."""
    monkeypatch.setattr("app.routes.topic.settings.api_key", "test-key")
    monkeypatch.setattr("app.routes.topic.settings.api_base_url", "https://api.example.com")
    monkeypatch.setattr("app.routes.topic.settings.model", "test-model")


def _fake_agent_returning(output: str | None):
    """Build a fake PydanticAI Agent whose ``run`` returns ``output``."""
    result = MagicMock()
    result.output = output
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=result)
    return fake_agent


def _fake_agent_raising(exc: BaseException):
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(side_effect=exc)
    return fake_agent


def test_refine_topic_requires_api_key(client, monkeypatch):
    monkeypatch.setattr("app.routes.topic.settings.api_key", "")
    resp = client.post("/api/topic/refine", json={"topic": "AI 教育"})
    assert resp.status_code == 400
    assert "API Key" in resp.json()["detail"]


def test_refine_topic_rejects_blank(client, patched_settings_with_key):
    resp = client.post("/api/topic/refine", json={"topic": "   "})
    assert resp.status_code == 400
    assert "不能为空" in resp.json()["detail"]


def test_refine_topic_success(client, patched_settings_with_key):
    fake_agent = _fake_agent_returning("AI 是否应在 K-12 教育中替代教师？")
    with patch("app.routes.topic.create_topic_refiner_agent", return_value=fake_agent):
        resp = client.post("/api/topic/refine", json={"topic": "AI 教育"})

    assert resp.status_code == 200
    assert resp.json() == {"refined_topic": "AI 是否应在 K-12 教育中替代教师？"}
    fake_agent.run.assert_awaited_once()


def test_refine_topic_auth_error(client, patched_settings_with_key):
    """A 401 from the model API maps to a friendly 'API Key 无效' message."""
    from pydantic_ai.exceptions import ModelHTTPError

    fake_agent = _fake_agent_raising(ModelHTTPError(401, "test-model", body=None))
    with patch("app.routes.topic.create_topic_refiner_agent", return_value=fake_agent):
        resp = client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 401
    assert "API Key" in resp.json()["detail"]


def test_refine_topic_not_found(client, patched_settings_with_key):
    """A 404 from the model API maps to a friendly model/URL message."""
    from pydantic_ai.exceptions import ModelHTTPError

    fake_agent = _fake_agent_raising(ModelHTTPError(404, "test-model", body=None))
    with patch("app.routes.topic.create_topic_refiner_agent", return_value=fake_agent):
        resp = client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 404
    assert "模型" in resp.json()["detail"]


def test_refine_topic_generic_error(client, patched_settings_with_key):
    fake_agent = _fake_agent_raising(RuntimeError("boom"))
    with patch("app.routes.topic.create_topic_refiner_agent", return_value=fake_agent):
        resp = client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 502
    assert "失败" in resp.json()["detail"]
    # Provider error text must not leak.
    assert "boom" not in resp.json()["detail"]


def test_refine_topic_other_model_http_error(client, patched_settings_with_key):
    """A ModelHTTPError with an unhandled status code (e.g. 500) collapses
    to the generic 502 path."""
    from pydantic_ai.exceptions import ModelHTTPError

    fake_agent = _fake_agent_raising(ModelHTTPError(500, "test-model", body=None))
    with patch("app.routes.topic.create_topic_refiner_agent", return_value=fake_agent):
        resp = client.post("/api/topic/refine", json={"topic": "话题"})

    assert resp.status_code == 502
    assert "失败" in resp.json()["detail"]

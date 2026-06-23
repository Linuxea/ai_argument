"""Debate lifecycle routes: start, stream (SSE), message, stop, resume, judge."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.deps import DebaterRepository, get_debater_repository, get_engine
from app.engine.debate import DebateEngine
from app.models import DebateConfig, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debate", tags=["debate"])

# SSE event types that terminate the stream.
TERMINAL_EVENTS = (
    "debate_end",
    "judge_result",
    "debate_paused",
    "debate_error",
    "judge_error",
)


# Strong references to background judge tasks. Without this, the only ref to
# the task is the one held by the event loop's weak set, which means GC can
# collect (and silently cancel) a long-running task mid-flight.
# See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def _safe_judge(engine: DebateEngine) -> None:
    """Run judgment with a safety net.

    ``DebateEngine.judge`` already emits a ``judge_error`` terminal event on
    internal failure, but this wrapper guarantees a terminal event even if the
    coroutine is cancelled or fails before reaching judge's own try/except —
    so the SSE consumer never hangs.

    The error event is routed through ``engine.emit_error`` (and thus the
    replay buffer) so reconnecting clients see the terminal state instead of
    hanging on keepalives.
    """
    try:
        await engine.judge()
    except Exception:
        logger.exception("Safe-judge wrapper caught unexpected error")
        await engine.emit_error("评判失败，请稍后重试", judge=True)


@router.post("/start")
async def start_debate(
    config: DebateConfig,
    engine: DebateEngine = Depends(get_engine),
    repository: DebaterRepository = Depends(get_debater_repository),
):
    """Start a new debate.

    The ``min_length=2`` and uniqueness invariants are enforced by
    ``DebateConfig`` itself (Pydantic 422 on violation); this handler only
    resolves names against the repository.
    """
    debater_map = {d.name: d for d in repository.list_all()}
    selected = [debater_map[name] for name in config.debater_names if name in debater_map]

    if len(selected) != len(config.debater_names):
        raise HTTPException(status_code=400, detail="Invalid debater name")

    # Global search kill-switch: disabling search for the debate forces every
    # selected debater's ``enable_search`` off. Copies are used so the shared
    # repository objects are never mutated, and a debater whose preset already
    # disables search is simply left as-is (the flag never grants search).
    if not config.search_enabled:
        selected = [d.model_copy(update={"enable_search": False}) for d in selected]

    try:
        engine.start(config.topic, selected, config.max_rounds)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": "started", "topic": config.topic}


@router.get("/stream")
async def debate_stream(
    request: Request,
    engine: DebateEngine = Depends(get_engine),
):
    """SSE endpoint for streaming debate events.

    Supports reconnect via the standard ``Last-Event-ID`` header: any events
    buffered in the engine's replay log with id > Last-Event-ID are replayed
    before the live stream resumes.

    Enforces single-consumer semantics: if a stream is already active, a
    second concurrent connection returns 409 so it cannot silently split
    events off the queue.
    """
    if not engine.acquire_consumer():
        raise HTTPException(
            status_code=409,
            detail="A stream is already active; close it before reconnecting.",
        )

    last_id_raw = request.headers.get("last-event-id", "0")
    try:
        last_event_id = int(last_id_raw)
    except (TypeError, ValueError):
        last_event_id = 0

    async def event_generator():
        try:
            # Replay any missed events first so reconnecting clients don't lose
            # the chunks emitted during the brief disconnect window.
            if last_event_id > 0 and engine.state:
                for ev in engine.events_since(last_event_id):
                    data = json.dumps(ev.payload)
                    yield f"id: {ev.id}\nevent: {ev.type}\ndata: {data}\n\n"
                    if ev.type in TERMINAL_EVENTS:
                        return

            # Start debate loop AFTER SSE consumer is connected
            engine.ensure_loop_running()

            while True:
                if engine.state:
                    try:
                        event = await asyncio.wait_for(
                            engine.event_queue.get(),
                            timeout=30.0,
                        )
                        data = json.dumps(event.payload)
                        id_line = f"id: {event.id}\n" if event.id else ""
                        yield f"{id_line}event: {event.type}\ndata: {data}\n\n"

                        if event.type in TERMINAL_EVENTS:
                            break
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                else:
                    break
        finally:
            engine.release_consumer()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/message")
async def inject_message(
    msg: UserMessage,
    engine: DebateEngine = Depends(get_engine),
):
    """Inject a user message into the debate."""
    if not engine.state or not engine.state.active:
        raise HTTPException(status_code=400, detail="No active debate")

    engine.inject_message(msg.message)
    return {"status": "injected"}


@router.post("/stop")
async def stop_debate(engine: DebateEngine = Depends(get_engine)):
    """Stop/pause the debate."""
    if engine.state:
        engine.stop()
        return {"status": "stopped"}
    raise HTTPException(status_code=400, detail="No active debate")


@router.post("/resume")
async def resume_debate(engine: DebateEngine = Depends(get_engine)):
    """Resume a paused debate."""
    if engine.state:
        engine.resume()
        # Loop will be started by SSE endpoint when consumer reconnects
        return {"status": "resumed", "needs_sse_reconnect": True}
    raise HTTPException(status_code=400, detail="No debate to resume")


@router.post("/judge")
async def judge_debate(engine: DebateEngine = Depends(get_engine)):
    """Request judge's analysis. Only allowed when debate is not actively running."""
    if not engine.state:
        raise HTTPException(status_code=400, detail="No active debate")

    if engine.state.active:
        raise HTTPException(
            status_code=400, detail="Please stop the debate before requesting a judgment"
        )

    if engine.judge_task and not engine.judge_task.done():
        raise HTTPException(status_code=409, detail="Judgment already in progress")

    task = asyncio.create_task(_safe_judge(engine))
    engine.judge_task = task
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return {"status": "judging"}

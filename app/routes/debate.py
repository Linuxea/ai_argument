"""Debate lifecycle routes: start, stream (SSE), message, stop, resume, judge."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import DebaterRepository, get_debater_repository, get_engine
from app.engine.debate import DebateEngine
from app.engine.state import Event
from app.models import DebateConfig, UserMessage

router = APIRouter(prefix="/api/debate", tags=["debate"])

# SSE event types that terminate the stream.
TERMINAL_EVENTS = (
    "debate_end",
    "judge_result",
    "debate_paused",
    "debate_error",
    "judge_error",
)


async def _safe_judge(engine: DebateEngine) -> None:
    """Run judgment with a safety net.

    ``DebateEngine.judge`` already emits a ``judge_error`` terminal event on
    internal failure, but this wrapper guarantees a terminal event even if the
    coroutine is cancelled or fails before reaching judge's own try/except —
    so the SSE consumer never hangs.
    """
    try:
        await engine.judge()
    except Exception as exc:
        await engine.event_queue.put(
            Event(type="judge_error", payload={"message": f"评判失败: {exc}"})
        )


@router.post("/start")
async def start_debate(
    config: DebateConfig,
    engine: DebateEngine = Depends(get_engine),
    repository: DebaterRepository = Depends(get_debater_repository),
):
    """Start a new debate."""
    if len(config.debater_names) < 2:
        raise HTTPException(status_code=400, detail="At least 2 debaters required")

    debater_map = {d.name: d for d in repository.list_all()}
    selected = [debater_map[name] for name in config.debater_names if name in debater_map]

    if len(selected) != len(config.debater_names):
        raise HTTPException(status_code=400, detail="Invalid debater name")

    engine.start(config.topic, selected, config.max_rounds)
    return {"status": "started", "topic": config.topic}


@router.get("/stream")
async def debate_stream(engine: DebateEngine = Depends(get_engine)):
    """SSE endpoint for streaming debate events."""
    async def event_generator():
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
                    yield f"event: {event.type}\ndata: {data}\n\n"

                    if event.type in TERMINAL_EVENTS:
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            else:
                break

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
        raise HTTPException(status_code=400, detail="Please stop the debate before requesting a judgment")

    asyncio.create_task(_safe_judge(engine))
    return {"status": "judging"}

"""Application factory for the AI Debate Chatroom.

``create_app()`` assembles the FastAPI application: settings, lifespan
(engine + repository on app.state), static mount, and route registration.
``main.py`` is now a thin shim that calls this factory.
"""
from __future__ import annotations

import asyncio
import json
import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from app.config import load_presets, settings
from app.deps import DebaterRepository
from app.engine.debate import DebateEngine
from app.engine.state import Event
from app.models import (
    CustomDebaterRequest,
    DebateConfig,
    Debater,
    RefineTopicRequest,
    UserMessage,
)

BASE_DIR = Path(__file__).resolve().parent.parent

_DEBATER_HOT_TAKES = [
    "You opened DevTools. The real debate is whether your code is the bug or the feature.",
    "Every bug is just a feature that lost the debate.",
    "In a debate between you and the code, the code always wins.",
    "The best debater is the one who knows when to stop arguing and start debugging.",
    "404: Interesting content not found. Just kidding. Here's a hot take instead.",
    "Console.log is just you arguing with your future self.",
    "Every CSS centering attempt is a debate between you and the universe.",
    "The real debate: tabs or spaces? (We use tabs. Fight us.)",
    "A good debater changes minds. A great debater changes the topic.",
    "DevTools: where you go to argue with your own frontend.",
]


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


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = DebateEngine(
            model=settings.model,
            base_url=settings.api_base_url,
            api_key=settings.api_key,
            brave_api_key=settings.brave_api_key,
        )
        app.state.debater_repository = DebaterRepository()
        # Cache index.html at startup so we don't do sync I/O per request.
        app.state.index_html = (BASE_DIR / "static" / "index.html").read_text()
        yield

    app = FastAPI(title="AI Debate Chatroom", lifespan=lifespan)
    # Seed app.state with defaults so routes are safe even if lifespan hasn't
    # run (e.g. TestClient used without a `with` context). Lifespan replaces
    # these with the real instances at startup.
    app.state.engine = None
    app.state.debater_repository = DebaterRepository()
    app.state.index_html = (BASE_DIR / "static" / "index.html").read_text()
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    """Register all HTTP routes on the given app (stage 4: closures over app.state)."""
    from openai import AuthenticationError, NotFoundError

    def _engine_or_400() -> DebateEngine:
        """Return the debate engine, or 400 if lifespan hasn't initialised it."""
        engine: DebateEngine | None = app.state.engine
        if engine is None:
            raise HTTPException(status_code=400, detail="Service not ready")
        return engine

    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    async def chrome_devtools_easter_egg():
        """Chrome DevTools well-known URI — returning unsolicited debate hot takes."""
        return {
            "message": random.choice(_DEBATER_HOT_TAKES),
            "debate_tip": "Remember: a strong argument addresses the counterargument head-on.",
            "api_notice": "This endpoint exists because Chrome DevTools requests it. "
                          "We figured we'd have some fun with it.",
            "surprise": "🔥 You found the easter egg! Not all heroes wear capes — some just open DevTools.",
        }

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main HTML page."""
        return app.state.index_html

    @app.get("/api/presets")
    async def get_presets():
        """Get all preset debaters."""
        return [d.model_dump() for d in load_presets()]

    @app.get("/api/debaters")
    async def get_all_debaters():
        """Get all available debaters (presets + custom)."""
        return [d.model_dump() for d in app.state.debater_repository.list_all()]

    @app.post("/api/debate/start")
    async def start_debate(config: DebateConfig):
        """Start a new debate."""
        engine = _engine_or_400()

        if len(config.debater_names) < 2:
            raise HTTPException(status_code=400, detail="At least 2 debaters required")

        repository: DebaterRepository = app.state.debater_repository
        debater_map = {d.name: d for d in repository.list_all()}
        selected = [debater_map[name] for name in config.debater_names if name in debater_map]

        if len(selected) != len(config.debater_names):
            raise HTTPException(status_code=400, detail="Invalid debater name")

        engine.start(config.topic, selected, config.max_rounds)
        return {"status": "started", "topic": config.topic}

    @app.get("/api/debate/stream")
    async def debate_stream():
        """SSE endpoint for streaming debate events."""
        engine = _engine_or_400()

        async def event_generator():
            # Start debate loop AFTER SSE consumer is connected
            engine.ensure_loop_running()

            while True:
                if engine.state:
                    try:
                        event = await asyncio.wait_for(
                            engine.event_queue.get(),
                            timeout=30.0
                        )
                        data = json.dumps(event.payload)
                        yield f"event: {event.type}\ndata: {data}\n\n"

                        if event.type in (
                            "debate_end",
                            "judge_result",
                            "debate_paused",
                            "debate_error",
                            "judge_error",
                        ):
                            break
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                else:
                    break

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )

    @app.post("/api/debate/message")
    async def inject_message(msg: UserMessage):
        """Inject a user message into the debate."""
        engine = _engine_or_400()
        if not engine.state or not engine.state.active:
            raise HTTPException(status_code=400, detail="No active debate")

        engine.inject_message(msg.message)
        return {"status": "injected"}

    @app.post("/api/debate/stop")
    async def stop_debate():
        """Stop/pause the debate."""
        engine = _engine_or_400()
        if engine.state:
            engine.stop()
            return {"status": "stopped"}
        raise HTTPException(status_code=400, detail="No active debate")

    @app.post("/api/debate/resume")
    async def resume_debate():
        """Resume a paused debate."""
        engine = _engine_or_400()
        if engine.state:
            engine.resume()
            # Loop will be started by SSE endpoint when consumer reconnects
            return {"status": "resumed", "needs_sse_reconnect": True}
        raise HTTPException(status_code=400, detail="No debate to resume")

    @app.post("/api/debate/judge")
    async def judge_debate():
        """Request judge's analysis. Only allowed when debate is not actively running."""
        engine = _engine_or_400()
        if not engine.state:
            raise HTTPException(status_code=400, detail="No active debate")

        if engine.state.active:
            raise HTTPException(status_code=400, detail="Please stop the debate before requesting a judgment")

        asyncio.create_task(_safe_judge(engine))
        return {"status": "judging"}

    @app.post("/api/debaters")
    async def create_debater(request: CustomDebaterRequest):
        """Create a custom debater."""
        debater = Debater(
            name=request.name,
            color=request.color,
            avatar=request.avatar,
            stance=request.stance,
            personality=request.personality,
            enable_search=request.enable_search,
        )
        if not await app.state.debater_repository.add(debater):
            raise HTTPException(status_code=409, detail="Debater name already exists")
        return {"status": "created", "debater": debater.model_dump()}

    @app.post("/api/topic/refine")
    async def refine_topic(request: RefineTopicRequest):
        """Use AI to refine and clarify a debate topic."""
        if not settings.api_key:
            raise HTTPException(status_code=400, detail="请先在设置中配置 API Key")

        if not request.topic or not request.topic.strip():
            raise HTTPException(status_code=400, detail="话题不能为空")

        prompt = f"""请将以下辩论话题优化为更清晰、更有辩论价值的表述。

原始话题: {request.topic}

要求:
1. 保持原始话题的核心立场和意图
2. 使表述更加明确、具体
3. 确保话题具有可辩性（存在不同观点）
4. 直接输出优化后的话题，不要添加任何解释或前缀

优化后的话题:"""

        try:
            client = AsyncOpenAI(base_url=settings.api_base_url, api_key=settings.api_key)
            response = await client.chat.completions.create(
                model=settings.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7,
            )
            refined_topic = response.choices[0].message.content.strip()
            return {"refined_topic": refined_topic}
        except AuthenticationError:
            raise HTTPException(status_code=401, detail="API Key 无效")
        except NotFoundError:
            raise HTTPException(status_code=404, detail="模型不存在或 API URL 不正确")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"话题优化失败: {e}")

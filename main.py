import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from models import Debater, DebateConfig, UserMessage, CustomDebaterRequest, RefineTopicRequest
from config import load_presets, settings
from debate_engine import DebateEngine

BASE_DIR = Path(__file__).parent

# Global state
debate_engine: DebateEngine = None
custom_debaters: list[Debater] = []
_cached_index_html: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global debate_engine, _cached_index_html
    debate_engine = DebateEngine(
        model=settings.model,
        base_url=settings.api_base_url,
        api_key=settings.api_key,
        brave_api_key=settings.brave_api_key,
    )
    # Cache index.html at startup so we don't do sync I/O on every request
    _cached_index_html = (BASE_DIR / "static" / "index.html").read_text()
    yield


app = FastAPI(title="AI Debate Chatroom", lifespan=lifespan)


# Serve static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    return _cached_index_html or (BASE_DIR / "static" / "index.html").read_text()


@app.get("/api/presets")
async def get_presets():
    """Get all preset debaters."""
    return [d.model_dump() for d in load_presets()]


@app.get("/api/debaters")
async def get_all_debaters():
    """Get all available debaters (presets + custom)."""
    presets = load_presets()
    return [d.model_dump() for d in presets] + [d.model_dump() for d in custom_debaters]


@app.post("/api/debate/start")
async def start_debate(config: DebateConfig):
    """Start a new debate."""
    global debate_engine

    if len(config.debater_names) < 2:
        raise HTTPException(status_code=400, detail="At least 2 debaters required")

    # Get debater objects, preserving the order from the frontend
    all_debaters = load_presets() + custom_debaters
    debater_map = {d.name: d for d in all_debaters}
    selected = [debater_map[name] for name in config.debater_names if name in debater_map]

    if len(selected) != len(config.debater_names):
        raise HTTPException(status_code=400, detail="Invalid debater name")

    debate_engine.start(config.topic, selected, config.max_rounds)

    return {"status": "started", "topic": config.topic}


@app.get("/api/debate/stream")
async def debate_stream():
    """SSE endpoint for streaming debate events."""
    async def event_generator():
        # Start debate loop AFTER SSE consumer is connected
        if debate_engine:
            debate_engine.ensure_loop_running()

        while True:
            if debate_engine and debate_engine.state:
                try:
                    event = await asyncio.wait_for(
                        debate_engine.event_queue.get(),
                        timeout=30.0
                    )
                    data = json.dumps(event.payload)
                    yield f"event: {event.type}\ndata: {data}\n\n"

                    if event.type in ("debate_end", "judge_result", "debate_paused"):
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
    if not debate_engine or not debate_engine.state or not debate_engine.state.active:
        raise HTTPException(status_code=400, detail="No active debate")

    debate_engine.inject_message(msg.message)
    return {"status": "injected"}


@app.post("/api/debate/stop")
async def stop_debate():
    """Stop/pause the debate."""
    if debate_engine and debate_engine.state:
        debate_engine.stop()
        return {"status": "stopped"}
    raise HTTPException(status_code=400, detail="No active debate")


@app.post("/api/debate/resume")
async def resume_debate():
    """Resume a paused debate."""
    if debate_engine and debate_engine.state:
        debate_engine.resume()
        # Loop will be started by SSE endpoint when consumer reconnects
        return {"status": "resumed"}
    raise HTTPException(status_code=400, detail="No debate to resume")


@app.post("/api/debate/judge")
async def judge_debate():
    """Request judge's analysis. Only allowed when debate is not actively running."""
    if not debate_engine or not debate_engine.state:
        raise HTTPException(status_code=400, detail="No active debate")

    if debate_engine.state.active:
        raise HTTPException(status_code=400, detail="Please stop the debate before requesting a judgment")

    asyncio.create_task(debate_engine.judge())
    return {"status": "judging"}


@app.post("/api/debaters")
async def create_debater(request: CustomDebaterRequest):
    """Create a custom debater."""
    global custom_debaters

    all_debaters = load_presets() + custom_debaters
    if any(d.name == request.name for d in all_debaters):
        raise HTTPException(status_code=409, detail="Debater name already exists")

    debater = Debater(
        name=request.name,
        color=request.color,
        avatar=request.avatar,
        stance=request.stance,
        personality=request.personality,
        enable_search=request.enable_search,
    )
    custom_debaters.append(debater)
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
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower():
            raise HTTPException(status_code=401, detail="API Key 无效")
        elif "404" in error_msg:
            raise HTTPException(status_code=404, detail="模型不存在或 API URL 不正确")
        else:
            raise HTTPException(status_code=502, detail=f"话题优化失败: {error_msg}")

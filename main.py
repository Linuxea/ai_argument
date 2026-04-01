import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from models import Debater, DebateConfig, UserMessage, CustomDebaterRequest, ApiSettings
from config import load_presets, settings
from llm_client import LLMClient
from debate_engine import DebateEngine


# Global state
debate_engine: DebateEngine = None
custom_debaters: list[Debater] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global debate_engine
    llm = LLMClient(
        base_url=settings.api_base_url,
        api_key=settings.api_key,
        model=settings.model
    )
    debate_engine = DebateEngine(llm_client=llm)
    yield


app = FastAPI(title="AI Debate Chatroom", lifespan=lifespan)


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open("static/index.html") as f:
        return f.read()


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

    # Get debater objects
    all_debaters = load_presets() + custom_debaters
    selected = [d for d in all_debaters if d.name in config.debater_names]

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

                    if event.type == "debate_end":
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
    if not debate_engine or not debate_engine.state:
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


@app.post("/api/settings")
async def update_settings(api_settings: ApiSettings):
    """Update API settings and recreate the LLM client."""
    global debate_engine

    settings.api_base_url = api_settings.api_url
    settings.api_key = api_settings.api_key
    settings.model = api_settings.model_name

    debate_engine.llm = LLMClient(
        base_url=settings.api_base_url,
        api_key=settings.api_key,
        model=settings.model
    )

    return {"status": "updated"}


@app.post("/api/debaters")
async def create_debater(request: CustomDebaterRequest):
    """Create a custom debater."""
    global custom_debaters

    debater = Debater(
        name=request.name,
        color=request.color,
        avatar=request.avatar,
        stance=request.stance,
        personality=request.personality
    )
    custom_debaters.append(debater)
    return {"status": "created", "debater": debater.model_dump()}

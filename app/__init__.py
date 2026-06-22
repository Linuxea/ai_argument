"""Application factory for the AI Debate Chatroom.

``create_app()`` assembles the FastAPI application: settings, lifespan
(engine + repository on app.state), static mount, and route registration.
``main.py`` is now a thin shim that calls this factory.
"""

from __future__ import annotations

import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.deps import DebaterRepository
from app.engine.debate import DebateEngine
from app.routes import debate as debate_routes
from app.routes import debaters as debater_routes
from app.routes import topic as topic_routes

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

    app.include_router(debate_routes.router)
    app.include_router(debater_routes.router)
    app.include_router(topic_routes.router)
    return app

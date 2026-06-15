"""FastAPI dependency providers and in-memory repositories.

These replace the module-level globals that previously lived in ``main.py``.
The engine and repository instances are stored on ``app.state`` during
``create_app`` lifespan startup; the providers here expose them to routes via
``Depends``.
"""
from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request

from app.config import Settings, load_presets, settings
from app.engine.debate import DebateEngine
from app.models import Debater


class DebaterRepository:
    """In-memory store for custom debaters, created during a session.

    Preset debaters live in ``presets.yaml`` and are loaded via
    ``load_presets()``; this repository only holds the user-defined ones.
    All mutating access is guarded by a lock so concurrent POSTs cannot race
    the name-uniqueness check (TOCTOU).
    """

    def __init__(self) -> None:
        self._debaters: list[Debater] = []
        self._lock = asyncio.Lock()

    def list_all(self) -> list[Debater]:
        """Return presets + custom debaters as a single list."""
        return [*load_presets(), *self._debaters]

    def list_custom(self) -> list[Debater]:
        return list(self._debaters)

    async def add(self, debater: Debater) -> bool:
        """Add a custom debater. Returns False if the name already exists."""
        async with self._lock:
            existing = {d.name for d in self.list_all()}
            if debater.name in existing:
                return False
            self._debaters.append(debater)
            return True

    def find(self, name: str) -> Debater | None:
        for d in self.list_all():
            if d.name == name:
                return d
        return None


def get_settings() -> Settings:
    """Return the global settings instance."""
    return settings


def get_engine(request: Request) -> DebateEngine:
    """Return the debate engine attached to app.state at startup.

    Raises HTTPException(400) if the engine hasn't been initialised (e.g. when
    lifespan hasn't run), so every debate route is uniformly guarded.
    """
    engine: DebateEngine | None = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=400, detail="Service not ready")
    return engine


def get_debater_repository(request: Request) -> DebaterRepository:
    """Return the custom-debater repository attached to app.state."""
    return request.app.state.debater_repository

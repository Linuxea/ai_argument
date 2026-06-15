"""Compatibility shim — real implementation now lives in :mod:`app.engine`.

Kept so existing ``from debate_engine import ...`` imports keep working
during the staged refactor. Removed in stage 6.
"""
from app.engine.debate import DebateEngine  # noqa: F401
from app.engine.state import DebateState, Event, Message  # noqa: F401

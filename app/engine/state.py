"""Data structures for debate state and the SSE event envelope.

Kept dependency-free (only stdlib + the ``Debater`` model) so it can be
imported without pulling in the PydanticAI stack. This is also why
``DebaterDeps`` lives here: ``app.tools`` needs it for its ``RunContext``
type parameter, but ``app.agents`` needs ``app.tools`` for the ``web_search``
tool registration — so the deps dataclass must live in a module that neither
imports (this one).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models import ArgumentSummary, Debater


@dataclass
class Message:
    """A single message in the debate history."""

    speaker: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DebateState:
    """Mutable state for an ongoing debate."""

    topic: str
    debaters: list[Debater]
    active: bool = True
    current_round: int = 0
    current_turn_index: int = 0
    history: list[Message] = field(default_factory=list)
    max_rounds: int | None = None
    argument_summaries: list[ArgumentSummary] = field(default_factory=list)


@dataclass
class Event:
    """SSE event structure.

    ``id`` is assigned by the engine when the event is queued; clients may
    pass ``Last-Event-ID`` on reconnect to request replay of events emitted
    since that id (see ``app.routes.debate.debate_stream``).
    """

    type: str
    payload: dict[str, Any]
    id: int = 0


@dataclass
class DebaterDeps:
    """Dependencies injected into each debater agent run.

    Lives here (not in ``app.agents``) so that ``app.tools`` can import it
    without creating a circular dependency with ``app.agents`` (which lazily
    imports ``app.tools.web_search`` for tool registration).
    """

    topic: str
    debater: Debater
    round_number: int
    max_rounds: int | None
    brave_api_key: str | None = None

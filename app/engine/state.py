"""Data structures for debate state and the SSE event envelope.

Kept dependency-free (only stdlib + the ``Debater`` model) so it can be
imported without pulling in the PydanticAI stack.
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
    """SSE event structure."""

    type: str
    payload: dict[str, Any]

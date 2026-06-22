"""EventBus: SSE event emission + replay buffer for Last-Event-ID reconnect.

Extracted from ``DebateEngine`` as part of the god-object refactor (M1).
The engine delegates all event emission here so the engine file can focus on
debate logic (turns, prompts, judging) rather than transport bookkeeping.

Responsibilities:
- Assign monotonic ids to each emitted event.
- Append to a bounded replay buffer (default 500) so reconnecting SSE
  consumers can request missed events via ``Last-Event-ID``.
- Provide ``emit_error`` as the public terminal-error surface used by
  routes (e.g. ``_safe_judge``).
"""

from __future__ import annotations

import asyncio

from app.engine.state import Event


class EventBus:
    """Monotonic-id event queue with a bounded replay buffer."""

    def __init__(self, max_log: int = 500) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.log: list[Event] = []
        self._max_log = max_log
        self._next_id = 1

    async def emit(self, event: Event) -> None:
        """Assign an id, append to the replay log, and enqueue the event."""
        event.id = self._next_id
        self._next_id += 1
        self.log.append(event)
        if len(self.log) > self._max_log:
            # Drop oldest. Clients that reconnect after dropping out of the
            # window get a partial replay (newest N events).
            del self.log[: -self._max_log]
        await self.queue.put(event)

    def events_since(self, last_id: int) -> list[Event]:
        """Return buffered events with id > ``last_id`` for SSE reconnects."""
        if last_id <= 0:
            return []
        # Linear scan is fine; buffer is bounded.
        return [e for e in self.log if e.id > last_id]

    async def emit_error(self, message: str, *, judge: bool = False) -> None:
        """Public terminal-error helper used by routes' safety wrappers.

        Routes through ``emit`` so reconnecting clients see terminal errors
        via Last-Event-ID replay (otherwise they'd hang on keepalives).

        Args:
            message: Localised user-facing message. MUST NOT contain raw
                exception text — log full exceptions server-side instead.
            judge: If True, emit ``judge_error``; otherwise ``debate_error``.
        """
        event_type = "judge_error" if judge else "debate_error"
        await self.emit(Event(type=event_type, payload={"message": message}))

    def reset(self) -> None:
        """Drop the queue and replay log; ids restart at 1."""
        self.queue = asyncio.Queue()
        self.log = []
        self._next_id = 1

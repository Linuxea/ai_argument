"""Core debate engine: state management, prompt building, turn order, SSE events."""
from __future__ import annotations

import asyncio
import json
import logging

from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
)
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)

from app.agents import (
    DebaterDeps,
    create_debater_agent,
    create_extractor_agent,
    create_judge_agent,
)
from app.engine.state import DebateState, Event, Message
from app.models import ArgumentSummary, Debater

logger = logging.getLogger(__name__)


class DebateEngine:
    """Core debate logic: state management, message building, turn order.

    Uses PydanticAI agents for LLM calls. Keeps state management and
    SSE event emission as the engine's responsibility.
    """

    def __init__(
        self,
        model: str,
        brave_api_key: str = "",
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.brave_api_key = brave_api_key
        self.debater_agent = create_debater_agent(model, base_url, api_key, enable_search=True)
        self.debater_agent_no_search = create_debater_agent(model, base_url, api_key, enable_search=False)
        self.judge_agent = create_judge_agent(model, base_url, api_key)
        self._extractor_agent = create_extractor_agent(model, base_url, api_key)
        self.state: DebateState | None = None
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._loop_task: asyncio.Task[None] | None = None
        # Per-debater PydanticAI message history (keyed by debater name)
        self._history: dict[str, list[ModelMessage]] = {}

    def start(
        self,
        topic: str,
        debaters: list[Debater],
        max_rounds: int | None = None,
    ) -> None:
        """Initialize a new debate.

        Raises:
            ValueError: If debaters list is empty or max_rounds is not positive.
        """
        if not debaters:
            raise ValueError("debaters list cannot be empty")
        if max_rounds is not None and max_rounds <= 0:
            raise ValueError("max_rounds must be greater than 0")

        # Cancel any running loop task to prevent ghost tasks
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()

        self.state = DebateState(
            topic=topic,
            debaters=debaters,
            max_rounds=max_rounds,
        )
        self.event_queue = asyncio.Queue()
        self._loop_task = None
        self._history = {d.name: [] for d in debaters}

    def ensure_loop_running(self) -> None:
        """Start the debate loop if state is active and loop isn't already running."""
        if self.state and self.state.active and self._loop_task is None:
            self._loop_task = asyncio.create_task(self._run_loop_and_cleanup())

    async def _run_loop_and_cleanup(self) -> None:
        """Run the debate loop and clean up the task reference when done.

        Any exception from the loop (e.g. an LLM provider error mid-stream)
        is captured and surfaced as a ``debate_error`` terminal SSE event so
        the connected client is never left waiting on keepalives forever.
        """
        try:
            await self.run_loop()
        except Exception as exc:
            logger.exception("Debate loop failed")
            if self.state:
                self.state.active = False
            await self.event_queue.put(
                Event(
                    type="debate_error",
                    payload={"message": f"辩论过程中出错: {exc}"},
                )
            )
        finally:
            self._loop_task = None

    def _build_user_prompt(self, debater: Debater) -> str:
        """Build the user prompt for this turn.

        Own messages are excluded - they're already in message_history
        as ModelResponse entries.
        """
        if not self.state.history:
            return (
                f"You are the first speaker. "
                f"No one has spoken yet - do NOT reference or quote anyone. "
                f"Present your opening argument on the topic: {self.state.topic}"
            )

        parts = [f"Debate topic: {self.state.topic}"]

        if self.state.argument_summaries:
            summary_lines = ["[Key arguments raised so far]:"]
            for s in self.state.argument_summaries:
                points_text = "; ".join(s.points)
                summary_lines.append(f"Round {s.round + 1} - {s.debater_name}: {points_text}")
            parts.append("\n".join(summary_lines))

        for msg in self.state.history:
            if msg.speaker == debater.name:
                continue
            parts.append(f"[{msg.speaker}]: {msg.content}")
        return "\n\n".join(parts)

    async def run_turn(self) -> None:
        """Execute a single debater's turn.

        Uses ``run_stream_events`` instead of ``run_stream`` so that tool
        calls are fully executed even when the model returns text *and* a
        tool call in the same response (``run_stream`` would treat the text
        as final output and skip the tool).
        """
        if not self.state or not self.state.active:
            return

        debater = self.state.debaters[self.state.current_turn_index]
        user_prompt = self._build_user_prompt(debater)
        deps = DebaterDeps(
            topic=self.state.topic,
            debater=debater,
            round_number=self.state.current_round,
            max_rounds=self.state.max_rounds,
            brave_api_key=self.brave_api_key,
        )

        await self.event_queue.put(
            Event(
                type="debater_start",
                payload={
                    "debater_name": debater.name,
                    "color": debater.color,
                    "avatar": debater.avatar,
                },
            )
        )

        full_text = ""
        current_query = ""
        result_all_messages = None
        _thinking_active = False

        agent = self.debater_agent if debater.enable_search else self.debater_agent_no_search

        async for event in agent.run_stream_events(
            user_prompt,
            deps=deps,
            message_history=self._history[debater.name],
        ):
            # Handle PartStartEvent — TextPart
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                _thinking_active = await self._end_thinking(_thinking_active)
                initial_content = event.part.content
                if initial_content:
                    full_text += initial_content
                    await self.event_queue.put(
                        Event(
                            type="debater_chunk",
                            payload={
                                "debater_name": debater.name,
                                "text_chunk": initial_content,
                            },
                        )
                    )
            # Handle PartStartEvent — ThinkingPart
            elif isinstance(event, PartStartEvent) and isinstance(event.part, ThinkingPart):
                _thinking_active = True
                initial = event.part.content
                if initial:
                    await self.event_queue.put(Event(
                        type="thinking_chunk",
                        payload={"debater_name": debater.name, "text_chunk": initial},
                    ))
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                _thinking_active = await self._end_thinking(_thinking_active)
                delta = event.delta.content_delta
                full_text += delta
                await self.event_queue.put(
                    Event(
                        type="debater_chunk",
                        payload={
                            "debater_name": debater.name,
                            "text_chunk": delta,
                        },
                    )
                )
            # Handle PartDeltaEvent — ThinkingPartDelta
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, ThinkingPartDelta):
                delta = event.delta.content_delta
                await self.event_queue.put(Event(
                    type="thinking_chunk",
                    payload={"debater_name": debater.name, "text_chunk": delta},
                ))
            elif isinstance(event, FunctionToolCallEvent):
                args = event.part.args
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                current_query = args.get("query", "") if isinstance(args, dict) else ""
                await self.event_queue.put(Event(type="debater_finalize", payload={}))
            elif isinstance(event, FunctionToolResultEvent):
                result_text = ""
                if event.result and event.result.content:
                    result_text = str(event.result.content)[:200]
                await self.event_queue.put(Event(
                    type="tool_call",
                    payload={
                        "debater_name": debater.name,
                        "tool_name": "web_search",
                        "query": current_query,
                        "result_summary": result_text,
                    },
                ))
            elif isinstance(event, AgentRunResultEvent):
                result_all_messages = event.result.all_messages()

        # If thinking was the last thing streamed, finalize it
        _thinking_active = await self._end_thinking(_thinking_active)

        # Update this debater's message history
        if result_all_messages is not None:
            self._history[debater.name] = result_all_messages
        self.state.history.append(Message(speaker=debater.name, content=full_text))

        await self.event_queue.put(
            Event(
                type="debater_end",
                payload={
                    "debater_name": debater.name,
                    "full_text": full_text,
                },
            )
        )

        await self._extract_key_points(debater.name, full_text, self.state.current_round)

        self._advance_turn()

    def _advance_turn(self) -> None:
        """Advance to the next debater's turn."""
        self.state.current_turn_index += 1

        if self.state.current_turn_index >= len(self.state.debaters):
            self.state.current_turn_index = 0
            self.state.current_round += 1

    async def _end_thinking(self, thinking_active: bool) -> bool:
        """Transition out of thinking mode if active.

        Emits a ``debater_finalize`` event when leaving thinking, and returns
        the new (always False) thinking state. Centralises the
        thinking→response transition that previously was copy-pasted inline.
        """
        if thinking_active:
            await self.event_queue.put(Event(type="debater_finalize", payload={}))
        return False

    async def run_loop(self) -> None:
        """Run the debate loop until stopped or max rounds reached."""
        while self.state and self.state.active:
            await self.run_turn()

            # Check for round end
            if self.state.current_turn_index == 0 and self.state.current_round > 0:
                await self.event_queue.put(
                    Event(
                        type="round_end",
                        payload={"round_number": self.state.current_round},
                    )
                )

                # Check max rounds
                if self.state.max_rounds and self.state.current_round >= self.state.max_rounds:
                    self.state.active = False
                    await self.event_queue.put(
                        Event(
                            type="debate_end",
                            payload={"reason": "Max rounds reached"},
                        )
                    )
                    return

        if self.state:
            await self.event_queue.put(
                Event(
                    type="debate_paused",
                    payload={"reason": "Stopped by user"},
                )
            )

    def inject_message(self, message: str) -> bool:
        """Add a user message to the debate history."""
        if self.state and self.state.active:
            self.state.history.append(Message(speaker="You", content=message))
            return True
        return False

    def stop(self) -> bool:
        """Pause the debate."""
        if self.state:
            self.state.active = False
            return True
        return False

    def resume(self) -> bool:
        """Resume a paused debate.

        Note: this only flips ``state.active`` back to True. The debate loop
        task is NOT restarted here — the loop exits when the debate is paused
        (see ``_run_loop_and_cleanup``). An SSE consumer must reconnect and
        call ``ensure_loop_running()`` for turns to actually resume. The
        ``/api/debate/resume`` endpoint signals this requirement back to the
        client via ``needs_sse_reconnect``.
        """
        if self.state:
            self.state.active = True
            return True
        return False

    async def _extract_key_points(
        self,
        debater_name: str,
        full_text: str,
        round_number: int,
    ) -> None:
        """Extract key claims from a debater's response using the extractor agent."""
        if not full_text.strip():
            return
        try:
            prompt = f"Speaker: {debater_name}\n\n{full_text}"
            result = await self._extractor_agent.run(prompt)
            data = json.loads(result.output)
            points = data.get("points", [])
            if points:
                self.state.argument_summaries.append(
                    ArgumentSummary(round=round_number, debater_name=debater_name, points=points)
                )
        except Exception:
            # Non-fatal: argument summaries enhance cross-round memory but
            # are not required for the debate to continue. Log so a silent
            # degradation of the MEMORY_INSTRUCTIONS feature is traceable.
            logger.warning(
                "Failed to extract key points for %s (round %d)",
                debater_name,
                round_number,
                exc_info=True,
            )

    async def judge(self) -> bool:
        """Generate a judge's analysis of the debate.

        On failure, emits a ``judge_error`` terminal event so the SSE
        consumer can terminate instead of hanging on keepalives.
        """
        if not self.state:
            return False

        transcript = f"Debate topic: {self.state.topic}\n\n"
        for msg in self.state.history:
            transcript += f"[{msg.speaker}]: {msg.content}\n\n"

        full_text = ""
        try:
            async with self.judge_agent.run_stream(transcript) as result:
                async for delta in result.stream_text(delta=True):
                    full_text += delta
                    await self.event_queue.put(
                        Event(
                            type="judge_chunk",
                            payload={"text_chunk": delta},
                        )
                    )
        except Exception as exc:
            logger.exception("Judge generation failed")
            await self.event_queue.put(
                Event(
                    type="judge_error",
                    payload={"message": f"评判失败: {exc}"},
                )
            )
            return False

        await self.event_queue.put(
            Event(
                type="judge_result",
                payload={"judgment_text": full_text},
            )
        )
        return True

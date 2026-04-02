import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.messages import ModelMessage
from models import Debater
from agents import create_debater_agent, create_judge_agent, DebaterDeps


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
    max_rounds: Optional[int] = None


@dataclass
class Event:
    """SSE event structure."""

    type: str
    payload: dict


class DebateEngine:
    """Core debate logic: state management, message building, turn order.

    Uses PydanticAI agents for LLM calls. Keeps state management and
    SSE event emission as the engine's responsibility.
    """

    def __init__(self, model: str, brave_api_key: str = ""):
        self.model = model
        self.brave_api_key = brave_api_key
        self.debater_agent = create_debater_agent(model)
        self.judge_agent = create_judge_agent(model)
        self.state: Optional[DebateState] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._loop_task: Optional[asyncio.Task] = None
        # Per-debater PydanticAI message history
        self._history: dict[str, list[ModelMessage]] = {}

    def start(self, topic: str, debaters: list[Debater], max_rounds: Optional[int] = None):
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

    def ensure_loop_running(self):
        """Start the debate loop if state is active and loop isn't already running."""
        if self.state and self.state.active and self._loop_task is None:
            self._loop_task = asyncio.create_task(self._run_loop_and_cleanup())

    async def _run_loop_and_cleanup(self):
        """Run the debate loop and clean up the task reference when done."""
        try:
            await self.run_loop()
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
        for msg in self.state.history:
            if msg.speaker == debater.name:
                continue
            parts.append(f"[{msg.speaker}]: {msg.content}")
        return "\n\n".join(parts)

    async def _handle_events(self, ctx, event_stream, debater_name: str):
        """Monitor agent execution, emit SSE events for tool calls."""
        current_query = ""

        async for event in event_stream:
            if isinstance(event, FunctionToolCallEvent):
                current_query = event.part.args.get("query", "")
            elif isinstance(event, FunctionToolResultEvent):
                result_text = ""
                if event.result and event.result.content:
                    result_text = str(event.result.content)[:200]
                await self.event_queue.put(Event(
                    type="tool_call",
                    payload={
                        "debater_name": debater_name,
                        "tool_name": "web_search",
                        "query": current_query,
                        "result_summary": result_text,
                    },
                ))

    async def run_turn(self):
        """Execute a single debater's turn."""
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
        async with self.debater_agent.run_stream(
            user_prompt,
            deps=deps,
            message_history=self._history[debater.name],
            event_stream_handler=lambda ctx, es: self._handle_events(ctx, es, debater.name),
        ) as result:
            async for delta in result.stream_text(delta=True):
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

        # Update this debater's message history
        self._history[debater.name] = result.all_messages()
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

        self._advance_turn()

    def _advance_turn(self):
        """Advance to the next debater's turn."""
        self.state.current_turn_index += 1

        if self.state.current_turn_index >= len(self.state.debaters):
            self.state.current_turn_index = 0
            self.state.current_round += 1

    async def run_loop(self):
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
                    type="debate_end",
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
        """Resume a paused debate."""
        if self.state:
            self.state.active = True
            return True
        return False

    async def judge(self) -> bool:
        """Generate a judge's analysis of the debate."""
        if not self.state:
            return False

        transcript = f"Debate topic: {self.state.topic}\n\n"
        for msg in self.state.history:
            transcript += f"[{msg.speaker}]: {msg.content}\n\n"

        full_text = ""
        async with self.judge_agent.run_stream(transcript) as result:
            async for delta in result.stream_text(delta=True):
                full_text += delta
                await self.event_queue.put(
                    Event(
                        type="judge_chunk",
                        payload={"text_chunk": delta},
                    )
                )

        await self.event_queue.put(
            Event(
                type="judge_result",
                payload={"judgment_text": full_text},
            )
        )
        return True

    def update_model(self, model: str):
        """Recreate agents when API settings change."""
        self.model = model
        self.debater_agent = create_debater_agent(model)
        self.judge_agent = create_judge_agent(model)

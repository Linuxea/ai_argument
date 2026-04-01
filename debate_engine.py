import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from models import Debater
from llm_client import LLMClient


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
    """Core debate logic: state management, message building, turn order."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.state: Optional[DebateState] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()

    def start(self, topic: str, debaters: list[Debater], max_rounds: Optional[int] = None):
        """Initialize a new debate."""
        self.state = DebateState(
            topic=topic,
            debaters=debaters,
            max_rounds=max_rounds
        )
        self.event_queue = asyncio.Queue()

    def build_messages(self, debater: Debater) -> list[dict]:
        """Build the messages array for a specific debater's API call."""
        messages = [
            {"role": "system", "content": debater.personality},
            {"role": "user", "content": f"Debate topic: {self.state.topic}"}
        ]

        for msg in self.state.history:
            if msg.speaker == debater.name:
                # This debater's own past responses
                messages.append({"role": "assistant", "content": msg.content})
            else:
                # Other speakers (including user)
                messages.append({
                    "role": "user",
                    "content": f"[{msg.speaker}]: {msg.content}"
                })

        return messages

    async def run_turn(self):
        """Execute a single debater's turn."""
        if not self.state or not self.state.active:
            return

        debater = self.state.debaters[self.state.current_turn_index]
        messages = self.build_messages(debater)

        await self.event_queue.put(Event(
            type="debater_start",
            payload={
                "debater_name": debater.name,
                "color": debater.color,
                "avatar": debater.avatar
            }
        ))

        full_text = ""
        async for chunk in self.llm.stream(messages):
            full_text += chunk
            await self.event_queue.put(Event(
                type="debater_chunk",
                payload={
                    "debater_name": debater.name,
                    "text_chunk": chunk
                }
            ))

        self.state.history.append(Message(speaker=debater.name, content=full_text))

        await self.event_queue.put(Event(
            type="debater_end",
            payload={
                "debater_name": debater.name,
                "full_text": full_text
            }
        ))

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
                await self.event_queue.put(Event(
                    type="round_end",
                    payload={"round_number": self.state.current_round}
                ))

                # Check max rounds
                if self.state.max_rounds and self.state.current_round >= self.state.max_rounds:
                    self.state.active = False
                    await self.event_queue.put(Event(
                        type="debate_end",
                        payload={"reason": "Max rounds reached"}
                    ))
                    return

        if self.state:
            await self.event_queue.put(Event(
                type="debate_end",
                payload={"reason": "Stopped by user"}
            ))

    def inject_message(self, message: str):
        """Add a user message to the debate history."""
        if self.state:
            self.state.history.append(Message(speaker="You", content=message))

    def stop(self):
        """Pause the debate."""
        if self.state:
            self.state.active = False

    def resume(self):
        """Resume a paused debate."""
        if self.state:
            self.state.active = True

    async def judge(self):
        """Generate a judge's analysis of the debate."""
        if not self.state:
            return

        judge_prompt = """You are an impartial debate judge. Analyze the debate and provide:
1. A brief summary of each debater's key arguments
2. Strengths and weaknesses of each position
3. Your overall assessment

Be fair, balanced, and insightful."""

        messages = [
            {"role": "system", "content": judge_prompt},
            {"role": "user", "content": f"Debate topic: {self.state.topic}"}
        ]

        for msg in self.state.history:
            messages.append({
                "role": "user",
                "content": f"[{msg.speaker}]: {msg.content}"
            })

        full_text = ""
        async for chunk in self.llm.stream(messages):
            full_text += chunk
            await self.event_queue.put(Event(
                type="judge_chunk",
                payload={"text_chunk": chunk}
            ))

        await self.event_queue.put(Event(
            type="judge_result",
            payload={"judgment_text": full_text}
        ))

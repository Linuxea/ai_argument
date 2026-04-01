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

    DEBATE_RULES = """\
You are a participant in a multi-party debate. Follow these rules:

- Use the same language as the debate topic.
- Keep each response concise: 80–200 words. Prefer shorter, sharper arguments over long essays.
- Respond directly to what others said. Engage with their actual points, don't just state your position.
- When you agree or disagree with a specific speaker, mention them by name (e.g. "I agree with The Analyst that..." or "The Optimist's point about... overlooks...").
- Back up claims with reasoning or examples. No bare assertions.
- Be professional and respectful. No personal attacks.
- Don't repeat yourself. Push the discussion forward each round.
- Express yourself naturally, like a real debater would. Do NOT use headers, labels, or numbered sections in your speech. No "Rebuttal:", "Argument:", "Evidence:" or similar formatting. Just speak.\
"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.state: Optional[DebateState] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()

    def start(self, topic: str, debaters: list[Debater], max_rounds: Optional[int] = None):
        """Initialize a new debate.

        Raises:
            ValueError: If debaters list is empty or max_rounds is not positive.
        """
        if not debaters:
            raise ValueError("debaters list cannot be empty")
        if max_rounds is not None and max_rounds <= 0:
            raise ValueError("max_rounds must be greater than 0")

        self.state = DebateState(
            topic=topic,
            debaters=debaters,
            max_rounds=max_rounds
        )
        self.event_queue = asyncio.Queue()

    def build_messages(self, debater: Debater) -> list[dict]:
        """Build the messages array for a specific debater's API call."""
        system_prompt = f"{self.DEBATE_RULES}\n\n---\n\n{debater.personality}"
        messages = [
            {"role": "system", "content": system_prompt},
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

    def inject_message(self, message: str) -> bool:
        """Add a user message to the debate history.

        Returns:
            bool: True if message was added, False if no active debate state.
        """
        if self.state:
            self.state.history.append(Message(speaker="You", content=message))
            return True
        return False

    def stop(self) -> bool:
        """Pause the debate.

        Returns:
            bool: True if debate was stopped, False if no active debate state.
        """
        if self.state:
            self.state.active = False
            return True
        return False

    def resume(self) -> bool:
        """Resume a paused debate.

        Returns:
            bool: True if debate was resumed, False if no active debate state.
        """
        if self.state:
            self.state.active = True
            return True
        return False

    async def judge(self) -> bool:
        """Generate a judge's analysis of the debate.

        Returns:
            bool: True if judgment was generated, False if no active debate state.
        """
        if not self.state:
            return False

        judge_prompt = """\
You are an impartial debate judge. Analyze the debate fairly and write your assessment \
in the same language as the debate topic.

Your judgment should include:
1. A short summary of each debater's position.
2. Strengths and weaknesses for each debater.
3. The most memorable exchange or turning point.
4. Your final verdict: who made the more compelling case, and why.

Be concise. Cite actual arguments from the debate. Do not let your own opinions on the \
topic influence your judgment.\
"""

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
        return True

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
- When you refer to another debater by name, wrap their name in double square brackets, e.g. [[The Optimist]], [[The Skeptic]]. This makes it clear who you are responding to.
- Back up claims with reasoning or examples. No bare assertions.
- Be professional and respectful. No personal attacks.
- Don't repeat yourself. Push the discussion forward each round.
- When rebutting opponents, do not just deny their claims — use each rebuttal as a stepping stone to deepen and advance your own argument. Build upward, don't spin in circles.
- Express yourself naturally, like a real debater would. Do NOT use headers, labels, or numbered sections in your speech. No "Rebuttal:", "Argument:", "Evidence:" or similar formatting. Just speak.\
"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.state: Optional[DebateState] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._loop_task: Optional[asyncio.Task] = None

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
            max_rounds=max_rounds
        )
        self.event_queue = asyncio.Queue()
        self._loop_task = None

    def ensure_loop_running(self):
        """Start the debate loop if state is active and loop isn't already running.

        Called by the SSE endpoint to ensure the loop starts only after the
        SSE consumer is connected, preventing early events from being lost.
        """
        if self.state and self.state.active and self._loop_task is None:
            self._loop_task = asyncio.create_task(self._run_loop_and_cleanup())

    async def _run_loop_and_cleanup(self):
        """Run the debate loop and clean up the task reference when done."""
        try:
            await self.run_loop()
        finally:
            self._loop_task = None

    STANCE_INSTRUCTIONS = {
        "for": "You support the topic. Argue in favor of it. Focus on rebutting arguments from the opposing side — find their flaws, press hard, and do not let weak points slide.",
        "against": "You oppose the topic. Argue against it. Focus on rebutting arguments from the supporting side — find their flaws, press hard, and do not let weak points slide.",
        "neutral": "You take a balanced view. Weigh evidence from both sides.",
    }

    def build_messages(self, debater: Debater) -> list[dict]:
        """Build the messages array for a specific debater's API call."""
        stance_instruction = self.STANCE_INSTRUCTIONS.get(debater.stance, self.STANCE_INSTRUCTIONS["neutral"])

        # Build round countdown context
        countdown = ""
        if self.state.max_rounds:
            current = self.state.current_round + 1
            remaining = self.state.max_rounds - self.state.current_round
            if remaining <= 1:
                countdown = (
                    f"This is round {current} of {self.state.max_rounds} — "
                    f"FINAL ROUND. Make your strongest closing argument. No holding back."
                )
            else:
                countdown = (
                    f"This is round {current} of {self.state.max_rounds}. "
                    f"There {'is' if remaining - 1 == 1 else 'are'} {remaining - 1} "
                    f"round{'s' if remaining - 1 != 1 else ''} remaining after this one."
                )

        system_prompt = (
            f"{self.DEBATE_RULES}\n\n---\n\n"
            f"Your stance: {stance_instruction}\n\n"
            f"---\n\n"
            f"{debater.personality}"
        )
        if countdown:
            system_prompt += f"\n\n---\n\n{countdown}"
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if not self.state.history:
            # First turn of the debate — no prior arguments exist.
            # Instruct the debater to give an opening statement, NOT a rebuttal.
            messages.append({
                "role": "user",
                "content": (
                    f"You are the first speaker. "
                    f"No one has spoken yet — do NOT reference or quote anyone. "
                    f"Present your opening argument on the topic: {self.state.topic}"
                )
            })
        else:
            messages.append({
                "role": "user",
                "content": f"Debate topic: {self.state.topic}"
            })
            for msg in self.state.history:
                if msg.speaker == debater.name:
                    messages.append({"role": "assistant", "content": msg.content})
                else:
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

        # Only add to history if not an error response
        if not full_text.startswith("[Error:"):
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
        if self.state and self.state.active:
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

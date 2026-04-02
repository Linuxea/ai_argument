# PydanticAI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the OpenAI SDK LLM layer with PydanticAI agents, preserving all existing behavior.

**Architecture:** One shared `DebaterAgent` + one `JudgeAgent` created via factory functions in `agents.py`. `DebateEngine` keeps state management and SSE events, delegates LLM calls to agents. Per-turn context injected via `DebaterDeps` + `instructions`.

**Tech Stack:** Python, PydanticAI, FastAPI, pydantic, asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `agents.py` | CREATE | `DebaterDeps` dataclass, `create_debater_agent()`, `create_judge_agent()` factory functions |
| `debate_engine.py` | REWRITE | State management, SSE events, turn loop — LLM calls via PydanticAI agents |
| `main.py` | MODIFY | Remove `LLMClient` import, update init and settings endpoint |
| `config.py` | MODIFY | Add `build_model_string()` helper |
| `llm_client.py` | DELETE | Replaced by PydanticAI |
| `tests/conftest.py` | REWRITE | Replace `MockLLMClient` with `MockStreamResult`/`MockDebateAgent` |
| `tests/test_debate_engine.py` | REWRITE | Adapt to new engine constructor and mock |
| `tests/test_llm_client.py` | DELETE | No longer relevant |
| `tests/test_main.py` | MODIFY | Fix debater name assertions (known failure), adapt to new init |
| `tests/test_config.py` | MODIFY | Add tests for `build_model_string()` |
| `requirements.txt` | MODIFY | Add `pydantic-ai>=1.0.0` |

---

### Task 1: Install PydanticAI dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add pydantic-ai to requirements**

Add `pydantic-ai>=1.0.0` to `requirements.txt`:

```
fastapi>=0.109.0
uvicorn>=0.27.0
openai>=1.12.0
pydantic>=2.5.0
pydantic-ai>=1.0.0
pyyaml>=6.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
```

- [ ] **Step 2: Install the dependency**

Run: `pip install pydantic-ai>=1.0.0`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pydantic-ai dependency"
```

---

### Task 2: Add `build_model_string()` to config.py

**Files:**
- Modify: `config.py`
- Create test: `tests/test_config.py` (update existing)

- [ ] **Step 1: Write failing test for `build_model_string`**

Add to `tests/test_config.py` (keep existing tests, add new ones):

```python
from config import build_model_string


def test_build_model_string_deepseek():
    result = build_model_string("https://api.deepseek.com", "deepseek-chat")
    assert result == "deepseek:deepseek-chat"


def test_build_model_string_openai():
    result = build_model_string("https://api.openai.com/v1", "gpt-4o")
    assert result == "openai:gpt-4o"


def test_build_model_string_unknown_provider():
    result = build_model_string("https://my-custom-api.com/v1", "my-model")
    assert result == "openai:my-model"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_build_model_string_deepseek -v`
Expected: FAIL with `ImportError: cannot import name 'build_model_string'`

- [ ] **Step 3: Implement `build_model_string`**

Add to `config.py`:

```python
def build_model_string(base_url: str, model: str) -> str:
    """Convert API settings to a PydanticAI model string.

    Examples:
        build_model_string("https://api.deepseek.com", "deepseek-chat")
        -> "deepseek:deepseek-chat"

        build_model_string("https://api.openai.com/v1", "gpt-4o")
        -> "openai:gpt-4o"
    """
    KNOWN_PROVIDERS = {
        "api.deepseek.com": "deepseek",
        "api.openai.com": "openai",
    }
    for host, provider in KNOWN_PROVIDERS.items():
        if host in base_url:
            return f"{provider}:{model}"
    return f"openai:{model}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add build_model_string helper for PydanticAI model IDs"
```

---

### Task 3: Create `agents.py` with agent factories

**Files:**
- Create: `agents.py`
- Create test: `tests/test_agents.py`

- [ ] **Step 1: Write `agents.py`**

```python
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from models import Debater


DEBATE_RULES = """\
You are a participant in a multi-party debate. Follow these rules:

- Use the same language as the debate topic.
- Keep each response concise: 80-200 words. Prefer shorter, sharper arguments over long essays.
- Respond directly to what others said. Engage with their actual points, don't just state your position.
- When you refer to another debater by name, wrap their name in double square brackets, e.g. [[The Optimist]], [[The Skeptic]]. This makes it clear who you are responding to.
- Back up claims with reasoning or examples. No bare assertions.
- Be professional and respectful. No personal attacks.
- Don't repeat yourself. Push the discussion forward each round.
- When rebutting opponents, do not just deny their claims - use each rebuttal as a stepping stone to deepen and advance your own argument. Build upward, don't spin in circles.
- Express yourself naturally, like a real debater would. Do NOT use headers, labels, or numbered sections in your speech. No "Rebuttal:", "Argument:", "Evidence:" or similar formatting. Just speak.\
"""

STANCE_INSTRUCTIONS = {
    "for": "You support the topic. Argue in favor of it. Focus on rebutting arguments from the opposing side - find their flaws, press hard, and do not let weak points slide.",
    "against": "You oppose the topic. Argue against it. Focus on rebutting arguments from the supporting side - find their flaws, press hard, and do not let weak points slide.",
    "neutral": "You take a balanced view. Weigh evidence from both sides.",
}

JUDGE_PROMPT = """\
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


@dataclass
class DebaterDeps:
    """Dependencies injected into each debater agent run."""

    topic: str
    debater: Debater
    round_number: int
    max_rounds: int | None


def create_debater_agent(model: str) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent configured for debate participants.

    Args:
        model: PydanticAI model string, e.g. "deepseek:deepseek-chat".

    Returns:
        Agent instance with dynamic instructions that compose
        DEBATE_RULES + stance + personality + round countdown from deps.
    """
    agent: Agent[DebaterDeps, str] = Agent(
        model,
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
    )
    return agent


def _build_debater_instructions(ctx: RunContext[DebaterDeps]) -> str:
    """Build system instructions from deps. Called fresh on every run."""
    debater = ctx.deps.debater
    stance = STANCE_INSTRUCTIONS.get(debater.stance, STANCE_INSTRUCTIONS["neutral"])

    parts = [
        DEBATE_RULES,
        f"Your stance: {stance}",
        debater.personality,
    ]

    # Round countdown
    if ctx.deps.max_rounds:
        current = ctx.deps.round_number + 1
        max_r = ctx.deps.max_rounds
        remaining = max_r - ctx.deps.round_number
        if remaining <= 1:
            parts.append(
                f"This is round {current} of {max_r} - "
                f"FINAL ROUND. Make your strongest closing argument. No holding back."
            )
        else:
            plural = "s" if remaining - 1 != 1 else ""
            parts.append(
                f"This is round {current} of {max_r}. "
                f"There {'is' if remaining - 1 == 1 else 'are'} {remaining - 1} "
                f"round{plural} remaining after this one."
            )

    return "\n\n---\n\n".join(parts)


def create_judge_agent(model: str) -> Agent[None, str]:
    """Create a PydanticAI Agent configured for debate judging.

    Args:
        model: PydanticAI model string, e.g. "deepseek:deepseek-chat".

    Returns:
        Agent instance with static judge instructions.
    """
    agent: Agent[None, str] = Agent(
        model,
        output_type=str,
        instructions=JUDGE_PROMPT,
    )
    return agent
```

- [ ] **Step 2: Write test for agent factories**

Create `tests/test_agents.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from agents import (
    create_debater_agent,
    create_judge_agent,
    DebaterDeps,
    DEBATE_RULES,
    STANCE_INSTRUCTIONS,
    JUDGE_PROMPT,
    _build_debater_instructions,
)
from models import Debater


def test_create_debater_agent_returns_agent():
    agent = create_debater_agent("test:model")
    assert agent is not None


def test_create_judge_agent_returns_agent():
    agent = create_judge_agent("test:model")
    assert agent is not None


def test_build_debater_instructions_contains_rules():
    debater = Debater(name="Test", personality="You are a test debater.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="AI in education",
        debater=debater,
        round_number=0,
        max_rounds=None,
    )

    instructions = _build_debater_instructions(ctx)

    assert "multi-party debate" in instructions
    assert "You are a test debater." in instructions
    assert "balanced view" in instructions  # default stance is neutral


def test_build_debater_instructions_with_for_stance():
    debater = Debater(
        name="Optimist",
        stance="for",
        personality="Be optimistic.",
    )
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="Test topic",
        debater=debater,
        round_number=0,
        max_rounds=3,
    )

    instructions = _build_debater_instructions(ctx)

    assert "support the topic" in instructions
    assert "This is round 1 of 3" in instructions


def test_build_debater_instructions_final_round():
    debater = Debater(
        name="Skeptic",
        stance="against",
        personality="Be skeptical.",
    )
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="Test topic",
        debater=debater,
        round_number=2,  # last round when max_rounds=3
        max_rounds=3,
    )

    instructions = _build_debater_instructions(ctx)

    assert "FINAL ROUND" in instructions
    assert "oppose the topic" in instructions


def test_debater_deps_dataclass():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(
        topic="AI ethics",
        debater=debater,
        round_number=1,
        max_rounds=5,
    )
    assert deps.topic == "AI ethics"
    assert deps.debater.name == "Test"
    assert deps.round_number == 1
    assert deps.max_rounds == 5
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: add PydanticAI agent factories for debater and judge"
```

---

### Task 4: Rewrite `debate_engine.py` to use PydanticAI agents

**Files:**
- Rewrite: `debate_engine.py`

- [ ] **Step 1: Write the new `debate_engine.py`**

```python
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

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

    def __init__(self, model: str):
        self.model = model
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
```

- [ ] **Step 2: Commit**

```bash
git add debate_engine.py
git commit -m "feat: rewrite debate_engine to use PydanticAI agents"
```

---

### Task 5: Update `main.py` initialization

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update `main.py`**

```python
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from models import Debater, DebateConfig, UserMessage, CustomDebaterRequest, ApiSettings
from config import load_presets, settings, build_model_string
from debate_engine import DebateEngine


# Global state
debate_engine: DebateEngine = None
custom_debaters: list[Debater] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global debate_engine
    model = build_model_string(settings.api_base_url, settings.model)
    debate_engine = DebateEngine(model=model)
    yield


app = FastAPI(title="AI Debate Chatroom", lifespan=lifespan)


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open("static/index.html") as f:
        return f.read()


@app.get("/api/presets")
async def get_presets():
    """Get all preset debaters."""
    return [d.model_dump() for d in load_presets()]


@app.get("/api/debaters")
async def get_all_debaters():
    """Get all available debaters (presets + custom)."""
    presets = load_presets()
    return [d.model_dump() for d in presets] + [d.model_dump() for d in custom_debaters]


@app.post("/api/debate/start")
async def start_debate(config: DebateConfig):
    """Start a new debate."""
    global debate_engine

    if len(config.debater_names) < 2:
        raise HTTPException(status_code=400, detail="At least 2 debaters required")

    # Get debater objects, preserving the order from the frontend
    all_debaters = load_presets() + custom_debaters
    debater_map = {d.name: d for d in all_debaters}
    selected = [debater_map[name] for name in config.debater_names if name in debater_map]

    if len(selected) != len(config.debater_names):
        raise HTTPException(status_code=400, detail="Invalid debater name")

    debate_engine.start(config.topic, selected, config.max_rounds)

    return {"status": "started", "topic": config.topic}


@app.get("/api/debate/stream")
async def debate_stream():
    """SSE endpoint for streaming debate events."""

    async def event_generator():
        # Start debate loop AFTER SSE consumer is connected
        if debate_engine:
            debate_engine.ensure_loop_running()

        while True:
            if debate_engine and debate_engine.state:
                try:
                    event = await asyncio.wait_for(
                        debate_engine.event_queue.get(), timeout=30.0
                    )
                    data = json.dumps(event.payload)
                    yield f"event: {event.type}\ndata: {data}\n\n"

                    if event.type in ("debate_end", "judge_result"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            else:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/debate/message")
async def inject_message(msg: UserMessage):
    """Inject a user message into the debate."""
    if not debate_engine or not debate_engine.state or not debate_engine.state.active:
        raise HTTPException(status_code=400, detail="No active debate")

    debate_engine.inject_message(msg.message)
    return {"status": "injected"}


@app.post("/api/debate/stop")
async def stop_debate():
    """Stop/pause the debate."""
    if debate_engine and debate_engine.state:
        debate_engine.stop()
        return {"status": "stopped"}
    raise HTTPException(status_code=400, detail="No active debate")


@app.post("/api/debate/resume")
async def resume_debate():
    """Resume a paused debate."""
    if debate_engine and debate_engine.state:
        debate_engine.resume()
        # Loop will be started by SSE endpoint when consumer reconnects
        return {"status": "resumed"}
    raise HTTPException(status_code=400, detail="No debate to resume")


@app.post("/api/debate/judge")
async def judge_debate():
    """Request judge's analysis. Only allowed when debate is not actively running."""
    if not debate_engine or not debate_engine.state:
        raise HTTPException(status_code=400, detail="No active debate")

    if debate_engine.state.active:
        raise HTTPException(
            status_code=400, detail="Please stop the debate before requesting a judgment"
        )

    asyncio.create_task(debate_engine.judge())
    return {"status": "judging"}


@app.get("/api/models")
async def list_models():
    """Fetch available models from the configured API provider."""
    try:
        client = AsyncOpenAI(base_url=settings.api_base_url, api_key=settings.api_key)
        models = await client.models.list()
        model_ids = sorted([m.id for m in models.data])
        return {"models": model_ids}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {str(e)}")


@app.post("/api/settings")
async def update_settings(api_settings: ApiSettings):
    """Update API settings and recreate agents. Empty values fall back to defaults."""
    global debate_engine

    if api_settings.api_url:
        settings.api_base_url = api_settings.api_url
    if api_settings.api_key:
        settings.api_key = api_settings.api_key
    if api_settings.model_name:
        settings.model = api_settings.model_name

    model = build_model_string(settings.api_base_url, settings.model)
    debate_engine.update_model(model)

    return {"status": "updated"}


@app.post("/api/debaters")
async def create_debater(request: CustomDebaterRequest):
    """Create a custom debater."""
    global custom_debaters

    all_debaters = load_presets() + custom_debaters
    if any(d.name == request.name for d in all_debaters):
        raise HTTPException(status_code=409, detail="Debater name already exists")

    debater = Debater(
        name=request.name,
        color=request.color,
        avatar=request.avatar,
        stance=request.stance,
        personality=request.personality,
    )
    custom_debaters.append(debater)
    return {"status": "created", "debater": debater.model_dump()}
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: update main.py to use PydanticAI-based DebateEngine"
```

---

### Task 6: Delete `llm_client.py`

**Files:**
- Delete: `llm_client.py`
- Delete: `tests/test_llm_client.py`

- [ ] **Step 1: Delete files**

```bash
rm llm_client.py tests/test_llm_client.py
```

- [ ] **Step 2: Verify no remaining imports of llm_client**

Run: `grep -r "llm_client" --include="*.py" .`
Expected: No matches (except possibly in the git history)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove llm_client.py and its tests, replaced by PydanticAI agents"
```

---

### Task 7: Rewrite test mocks and test files

**Files:**
- Rewrite: `tests/conftest.py`
- Rewrite: `tests/test_debate_engine.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Rewrite `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
from pydantic_ai.messages import ModelMessage


class MockStreamResult:
    """Mimics the async context manager returned by Agent.run_stream()."""

    def __init__(self, text: str):
        self._text = text
        self._messages: list[ModelMessage] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def stream_text(self, delta=True):
        words = self._text.split()
        for i, word in enumerate(words):
            if delta:
                yield word if i == 0 else " " + word
            else:
                yield " ".join(words[: i + 1])

    def all_messages(self) -> list[ModelMessage]:
        return self._messages


class MockDebateAgent:
    """Mock that replaces both debater_agent and judge_agent for testing."""

    def __init__(self, responses: list[str] = None):
        self.responses = responses or ["This is a mock response."]
        self.call_count = 0
        self.last_user_prompt = None

    def run_stream(self, user_prompt: str, **kwargs):
        self.last_user_prompt = user_prompt
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MockStreamResult(response)


@pytest.fixture
def mock_agent():
    return MockDebateAgent()
```

- [ ] **Step 2: Rewrite `tests/test_debate_engine.py`**

```python
# tests/test_debate_engine.py
import pytest
from unittest.mock import patch, MagicMock

from debate_engine import DebateEngine, DebateState, Message
from models import Debater
from tests.conftest import MockDebateAgent


def _make_engine(responses=None):
    """Create a DebateEngine with mocked agents."""
    mock = MockDebateAgent(responses=responses)
    engine = DebateEngine(model="test:model")
    engine.debater_agent = mock
    engine.judge_agent = MockDebateAgent(responses=responses or ["Judgment."])
    return engine, mock


def test_build_user_prompt_first_turn():
    engine, _ = _make_engine()
    debater = Debater(name="Test Debater", personality="You are a test debater.")
    engine.state = DebateState(topic="Should AI replace teachers?", debaters=[debater])

    prompt = engine._build_user_prompt(debater)

    assert "first speaker" in prompt
    assert "Should AI replace teachers?" in prompt


def test_build_user_prompt_subsequent_turn():
    engine, _ = _make_engine()
    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")

    engine.state = DebateState(
        topic="AI in education",
        debaters=[skeptic, optimist],
        history=[
            Message(speaker="Skeptic", content="Teachers are irreplaceable."),
            Message(speaker="Optimist", content="AI can enhance learning."),
            Message(speaker="You", content="What about special needs?"),
        ],
    )

    prompt = engine._build_user_prompt(skeptic)

    # Skeptic's own messages should be excluded
    assert "Teachers are irreplaceable." not in prompt
    # Other speakers should appear
    assert "[Optimist]: AI can enhance learning." in prompt
    assert "[You]: What about special needs?" in prompt
    assert "Debate topic: AI in education" in prompt


def test_advance_turn_round_robin():
    engine, _ = _make_engine(responses=["Response A", "Response B"])

    debater_a = Debater(name="A", personality="You are A.")
    debater_b = Debater(name="B", personality="You are B.")

    engine.state = DebateState(topic="Test topic", debaters=[debater_a, debater_b])

    assert engine.state.current_turn_index == 0
    assert engine.state.current_round == 0

    engine._advance_turn()
    assert engine.state.current_turn_index == 1
    assert engine.state.current_round == 0

    engine._advance_turn()
    assert engine.state.current_turn_index == 0
    assert engine.state.current_round == 1


def test_inject_message_adds_to_history():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    engine.inject_message("This is my comment.")

    assert len(engine.state.history) == 1
    assert engine.state.history[0].speaker == "You"
    assert engine.state.history[0].content == "This is my comment."


def test_stop_sets_inactive():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    engine.stop()

    assert engine.state.active is False


def test_resume_sets_active():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    engine.resume()

    assert engine.state.active is True


def test_start_raises_error_on_empty_debaters():
    engine, _ = _make_engine()

    with pytest.raises(ValueError, match="debaters list cannot be empty"):
        engine.start(topic="Test topic", debaters=[])


def test_start_raises_error_on_zero_max_rounds():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")

    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        engine.start(topic="Test topic", debaters=[debater], max_rounds=0)


def test_start_raises_error_on_negative_max_rounds():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")

    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        engine.start(topic="Test topic", debaters=[debater], max_rounds=-1)


def test_inject_message_returns_true_when_state_exists():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    result = engine.inject_message("Test message")

    assert result is True


def test_inject_message_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = engine.inject_message("Test message")

    assert result is False


def test_stop_returns_true_when_state_exists():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    result = engine.stop()

    assert result is True


def test_stop_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = engine.stop()

    assert result is False


def test_resume_returns_true_when_state_exists():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    result = engine.resume()

    assert result is True


def test_resume_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = engine.resume()

    assert result is False


def test_start_initializes_per_debater_history():
    engine, _ = _make_engine()
    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")

    engine.start(topic="Test", debaters=[skeptic, optimist])

    assert "Skeptic" in engine._history
    assert "Optimist" in engine._history
    assert engine._history["Skeptic"] == []
    assert engine._history["Optimist"] == []


@pytest.mark.asyncio
async def test_run_turn_emits_correct_events():
    engine, mock = _make_engine(responses=["Hello world from debater."])

    debater = Debater(name="Alice", personality="You are Alice.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "debater_start" in event_types
    assert "debater_chunk" in event_types
    assert "debater_end" in event_types

    start_event = next(e for e in events if e.type == "debater_start")
    assert start_event.payload["debater_name"] == "Alice"

    end_event = next(e for e in events if e.type == "debater_end")
    assert end_event.payload["debater_name"] == "Alice"
    assert "Hello world from debater." in end_event.payload["full_text"]


@pytest.mark.asyncio
async def test_run_turn_adds_message_to_history():
    engine, mock = _make_engine(responses=["This is my argument."])

    debater = Debater(name="Bob", personality="You are Bob.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    await engine.run_turn()

    assert len(engine.state.history) == 1
    assert engine.state.history[0].speaker == "Bob"
    assert "This is my argument." in engine.state.history[0].content


@pytest.mark.asyncio
async def test_run_turn_does_nothing_when_state_is_none():
    engine, _ = _make_engine()

    await engine.run_turn()

    assert engine.event_queue.empty()


@pytest.mark.asyncio
async def test_run_turn_does_nothing_when_not_active():
    engine, _ = _make_engine()

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=False)

    await engine.run_turn()

    assert engine.event_queue.empty()
    assert len(engine.state.history) == 0


@pytest.mark.asyncio
async def test_run_loop_respects_max_rounds():
    engine, _ = _make_engine(responses=["Argument 1", "Argument 2"])

    debater_a = Debater(name="A", personality="You are A.")
    debater_b = Debater(name="B", personality="You are B.")

    engine.state = DebateState(
        topic="Test topic", debaters=[debater_a, debater_b], max_rounds=2
    )

    await engine.run_loop()

    assert engine.state.current_round == 2
    assert engine.state.active is False

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    end_events = [e for e in events if e.type == "debate_end"]
    assert len(end_events) == 1
    assert "Max rounds reached" in end_events[0].payload["reason"]


@pytest.mark.asyncio
async def test_run_loop_emits_round_end_event():
    engine, _ = _make_engine(responses=["Arg"])

    debater = Debater(name="Solo", personality="Solo debater.")
    engine.state = DebateState(topic="Test topic", debaters=[debater], max_rounds=2)

    await engine.run_loop()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    round_end_events = [e for e in events if e.type == "round_end"]
    assert len(round_end_events) == 2


@pytest.mark.asyncio
async def test_run_loop_stops_when_debate_stopped():
    engine, _ = _make_engine(responses=["Response"])

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater], active=True)

    engine.stop()

    await engine.run_loop()

    assert len(engine.state.history) == 0


@pytest.mark.asyncio
async def test_judge_returns_true_when_state_exists():
    engine, _ = _make_engine(responses=["My judgment is..."])

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    result = await engine.judge()

    assert result is True


@pytest.mark.asyncio
async def test_judge_returns_false_when_no_state():
    engine, _ = _make_engine()

    result = await engine.judge()

    assert result is False


@pytest.mark.asyncio
async def test_judge_emits_correct_events():
    engine, _ = _make_engine(responses=["The winner is..."])

    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])

    await engine.judge()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "judge_chunk" in event_types
    assert "judge_result" in event_types

    judge_result = next(e for e in events if e.type == "judge_result")
    assert "The winner is..." in judge_result.payload["judgment_text"]


def test_update_model_recreates_agents():
    engine, _ = _make_engine()

    old_debater = engine.debater_agent
    old_judge = engine.judge_agent

    engine.update_model("new:model")

    assert engine.model == "new:model"
    assert engine.debater_agent is not old_debater
    assert engine.judge_agent is not old_judge
```

- [ ] **Step 3: Update `tests/test_main.py`**

Fix the known failing assertions (Chinese preset names) and keep the test for min debaters:

```python
import pytest
from fastapi.testclient import TestClient


def test_get_presets_returns_debaters():
    from main import app

    client = TestClient(app)

    response = client.get("/api/presets")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Preset names are in Chinese (see presets.yaml)
    assert data[0]["name"] == "质疑者"
    assert data[1]["name"] == "乐观派"
    assert data[2]["name"] == "分析家"


def test_get_root_serves_html():
    from main import app

    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_start_debate_validates_min_debaters():
    from main import app

    client = TestClient(app)

    response = client.post(
        "/api/debate/start", json={"topic": "Test topic", "debater_names": ["质疑者"]}
    )

    assert response.status_code == 400
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_debate_engine.py tests/test_main.py
git commit -m "test: rewrite test mocks and test files for PydanticAI migration"
```

---

### Task 8: Run full test suite and verify server starts

**Files:**
- No file changes (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS, 0 failures

- [ ] **Step 2: Start the server and verify it boots**

Run: `python -m uvicorn main:app --port 8000`
Expected: Server starts without import errors or warnings. (Ctrl+C to stop)

- [ ] **Step 3: Verify imports are clean**

Run: `python -c "from debate_engine import DebateEngine; from agents import create_debater_agent, create_judge_agent; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit any remaining fixes if needed**

If any fixes were required during verification:

```bash
git add -A
git commit -m "fix: address issues found during verification"
```

---

### Task 9: Clean up and final commit

**Files:**
- Verify all changes

- [ ] **Step 1: Verify no references to old code remain**

Run: `grep -r "LLMClient\|llm_client\|from openai import.*AsyncOpenAI" --include="*.py" . | grep -v test_main | grep -v main.py`
Expected: No matches (main.py keeps AsyncOpenAI for /api/models)

- [ ] **Step 2: Verify git status is clean**

Run: `git status`
Expected: nothing to commit, working tree clean

- [ ] **Step 3: Final log check**

Run: `git log --oneline -10`
Verify all migration commits are present and in order.

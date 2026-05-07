# Debater Intelligence Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI debaters behave like skilled human debaters through strategic concession, dynamic strategy adaptation, and cross-round memory.

**Architecture:** Three prompt-layer features injected into `_build_debater_instructions` for Round 2+. One feature (memory) adds an extractor agent that runs after each turn to summarize key arguments. Frontend adds concession markup rendering with CSS styling.

**Tech Stack:** Python/FastAPI backend with PydanticAI agents, vanilla JS frontend, CSS custom properties.

**Spec:** `docs/superpowers/specs/2026-05-07-debater-intelligence-design.md`

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `models.py` | Modify | Add `ArgumentSummary` dataclass |
| `agents.py` | Modify | Add 4 prompt constants + `create_extractor_agent` + modify `_build_debater_instructions` |
| `debate_engine.py` | Modify | Add `_extractor_agent`, `_extract_key_points`, modify `_build_user_prompt`, `run_turn`, `update_model` |
| `tests/conftest.py` | Modify | Add `run` method to `MockDebateAgent` |
| `tests/test_agents.py` | Modify | Tests for prompt constants and injection |
| `tests/test_debate_engine.py` | Modify | Tests for extraction, summaries, integration |
| `static/app.js` | Modify | Add concession regex in `renderContent` |
| `static/style.css` | Modify | Add `.concession` styles |

---

### Task 1: Add ArgumentSummary dataclass

**Files:**
- Modify: `models.py`
- Test: `tests/test_debate_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_debate_engine.py` after the existing imports:

```python
from models import ArgumentSummary
```

Add test at the end of the file:

```python
def test_argument_summary_creation():
    summary = ArgumentSummary(round=1, debater_name="Alice", points=["Claim A", "Claim B"])
    assert summary.round == 1
    assert summary.debater_name == "Alice"
    assert summary.points == ["Claim A", "Claim B"]


def test_argument_summary_default_points():
    summary = ArgumentSummary(round=0, debater_name="Bob")
    assert summary.points == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_debate_engine.py::test_argument_summary_creation -v`
Expected: FAIL with `ImportError: cannot import name 'ArgumentSummary' from 'models'`

- [ ] **Step 3: Write minimal implementation**

Add to the end of `models.py`:

```python
from dataclasses import dataclass, field


@dataclass
class ArgumentSummary:
    round: int
    debater_name: str
    points: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_debate_engine.py::test_argument_summary_creation tests/test_debate_engine.py::test_argument_summary_default_points -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_debate_engine.py
git commit -m "feat: add ArgumentSummary dataclass for debate memory"
```

---

### Task 2: Add prompt constants and extractor prompt

**Files:**
- Modify: `agents.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_agents.py` imports:

```python
from agents import (
    create_debater_agent,
    create_debater_agent_no_search,
    create_judge_agent,
    DebaterDeps,
    DEBATE_RULES,
    STANCE_INSTRUCTIONS,
    JUDGE_PROMPT,
    _build_debater_instructions,
    CONCESSION_INSTRUCTIONS,
    STRATEGY_INSTRUCTIONS,
    MEMORY_INSTRUCTIONS,
    EXTRACT_POINTS_PROMPT,
)
```

Add tests at the end of the file:

```python
def test_concession_instructions_exists():
    assert isinstance(CONCESSION_INSTRUCTIONS, str)
    assert len(CONCESSION_INSTRUCTIONS) > 50
    assert "退让" in CONCESSION_INSTRUCTIONS


def test_strategy_instructions_exists():
    assert isinstance(STRATEGY_INSTRUCTIONS, str)
    assert len(STRATEGY_INSTRUCTIONS) > 50
    assert "adapt" in STRATEGY_INSTRUCTIONS.lower() or "strategy" in STRATEGY_INSTRUCTIONS.lower()


def test_memory_instructions_exists():
    assert isinstance(MEMORY_INSTRUCTIONS, str)
    assert len(MEMORY_INSTRUCTIONS) > 50
    assert "reference" in MEMORY_INSTRUCTIONS.lower() or "earlier" in MEMORY_INSTRUCTIONS.lower()


def test_extract_points_prompt_exists():
    assert isinstance(EXTRACT_POINTS_PROMPT, str)
    assert "points" in EXTRACT_POINTS_PROMPT.lower()
    assert "json" in EXTRACT_POINTS_PROMPT.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents.py::test_concession_instructions_exists tests/test_agents.py::test_strategy_instructions_exists tests/test_agents.py::test_memory_instructions_exists tests/test_agents.py::test_extract_points_prompt_exists -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write implementation**

Add to `agents.py` after the `JUDGE_PROMPT` constant (after line 113), before `DebaterDeps`:

```python
CONCESSION_INSTRUCTIONS = """\
## Strategic Concession

A skilled debater knows when to yield ground to gain credibility:

- When an opponent makes a valid point on a **non-core** issue, acknowledge it honestly using the markup: \
[退让]your acknowledgement here[/退让]
- After conceding, immediately **reframe** the issue or pivot to a stronger argument — never concede without \
following up with a stronger position
- Never concede your **core** position — only peripheral or secondary points
- Use concessions strategically: they build trust and make your strongest arguments more credible
- A good concession sounds like: "You raise a fair point about X, but that actually reinforces my argument \
because Y"
"""

STRATEGY_INSTRUCTIONS = """\
## Dynamic Strategy

Before responding, observe your opponent's argumentation style and adapt your counter-strategy:

- If they rely on **data and statistics** → counter with human stories, emotional narratives, and real-world impact
- If they use **emotional narratives** → counter with rigorous logic, statistics, and systematic analysis
- If they are **aggressive and combative** → stay calm, measured, and precise — composure beats aggression
- If they are **cautious and reserved** → seize the initiative, push harder, force engagement
- If they argue in **abstract terms** → ground the debate in concrete examples and practical consequences

Your adaptation should feel natural and seamless — not mechanical or formulaic. Choose ONE dominant \
counter-strategy per round.
"""

MEMORY_INSTRUCTIONS = """\
## Memory and Citation

Build narrative continuity across rounds:

- **Reference specific arguments** from earlier rounds: "In round 1, [[Name]] claimed X..."
- **Point out contradictions** if an opponent's position has shifted between rounds
- **Track unanswered questions**: if you raised a challenge and no one addressed it, raise it again explicitly
- **Build on allies' arguments**: "As [[Name]] demonstrated earlier..." — strengthen shared positions
- **Evolve your own arguments** — do not repeat previous points verbatim; deepen and extend them each round
- Use the "[Key arguments raised so far]" section provided in the conversation to track what has been said
"""

EXTRACT_POINTS_PROMPT = """\
You are an argument extraction tool. Extract 2-3 key claims from the debate argument below.

Return ONLY a JSON object with this exact format:
{"points": ["claim 1", "claim 2", "claim 3"]}

Rules:
- Each claim should be one concise sentence
- Extract the strongest, most distinct arguments
- Do not paraphrase — keep the speaker's intent
- If fewer than 2 meaningful claims exist, extract whatever is available
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py::test_concession_instructions_exists tests/test_agents.py::test_strategy_instructions_exists tests/test_agents.py::test_memory_instructions_exists tests/test_agents.py::test_extract_points_prompt_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: add prompt constants for concession, strategy, memory, and extraction"
```

---

### Task 3: Inject new instructions into debater prompt for Round 2+

**Files:**
- Modify: `agents.py` (function `_build_debater_instructions`)
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write the failing tests**

Add tests at the end of `tests/test_agents.py`:

```python
def test_build_debater_instructions_includes_concession_for_round_2():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=1, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "退让" in instructions


def test_build_debater_instructions_excludes_concession_for_round_0():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=0, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "退让" not in instructions


def test_build_debater_instructions_includes_strategy_for_round_2():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=1, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Dynamic Strategy" in instructions


def test_build_debater_instructions_includes_memory_for_round_2():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=2, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Memory and Citation" in instructions


def test_build_debater_instructions_excludes_new_instructions_for_round_0():
    debater = Debater(name="Test", stance="正方", personality="Test.")
    ctx = MagicMock()
    ctx.deps = DebaterDeps(topic="Test", debater=debater, round_number=0, max_rounds=3)
    instructions = _build_debater_instructions(ctx)
    assert "Dynamic Strategy" not in instructions
    assert "Memory and Citation" not in instructions
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents.py::test_build_debater_instructions_includes_concession_for_round_2 tests/test_agents.py::test_build_debater_instructions_excludes_concession_for_round_0 -v`
Expected: FAIL — "退让" not found in instructions at round 1

- [ ] **Step 3: Write implementation**

Modify `_build_debater_instructions` in `agents.py`. Replace the `parts` assembly block (the section from `parts = [` to `return "\n\n---\n\n".join(parts)`):

```python
    parts = [
        date_context,
        DEBATE_RULES,
    ]

    if ctx.deps.round_number >= 1:
        parts.append(CONCESSION_INSTRUCTIONS)
        parts.append(STRATEGY_INSTRUCTIONS)
        parts.append(MEMORY_INSTRUCTIONS)

    parts.extend([
        f"Your stance: {stance}",
        debater.personality,
    ])

    if debater.enable_search:
        parts.append(SEARCH_INSTRUCTIONS)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS (including existing tests — verify none broke)

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: inject concession, strategy, and memory instructions for Round 2+"
```

---

### Task 4: Add extractor agent

**Files:**
- Modify: `agents.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agents.py`:

```python
def test_create_extractor_agent_returns_agent():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent is not None


def test_extractor_agent_has_no_tools():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    tool_names = list(agent._function_toolset.tools.keys())
    assert len(tool_names) == 0


def test_extractor_agent_has_no_thinking():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_extractor_agent("deepseek-chat", "https://api.example.com", "test-key")
    settings = agent.model_settings or {}
    assert settings.get("thinking") is not True
```

Add `create_extractor_agent` to the imports:

```python
from agents import (
    create_debater_agent,
    create_debater_agent_no_search,
    create_judge_agent,
    create_extractor_agent,
    DebaterDeps,
    DEBATE_RULES,
    STANCE_INSTRUCTIONS,
    JUDGE_PROMPT,
    _build_debater_instructions,
    CONCESSION_INSTRUCTIONS,
    STRATEGY_INSTRUCTIONS,
    MEMORY_INSTRUCTIONS,
    EXTRACT_POINTS_PROMPT,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_create_extractor_agent_returns_agent -v`
Expected: FAIL with `ImportError: cannot import name 'create_extractor_agent'`

- [ ] **Step 3: Write implementation**

Add to `agents.py` after `create_judge_agent` function:

```python
def create_extractor_agent(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[None, str]:
    """Create a lightweight agent for extracting key argument points."""
    agent: Agent[None, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=None,
        output_type=str,
        instructions=EXTRACT_POINTS_PROMPT,
        tools=[],
    )
    return agent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: add create_extractor_agent for argument point extraction"
```

---

### Task 5: Update test infrastructure — add `run` method to MockDebateAgent

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add `run` method to `MockDebateAgent`**

Add the following method to the `MockDebateAgent` class in `tests/conftest.py`, after the `run_stream` method:

```python
    async def run(self, user_prompt: str, **kwargs):
        """For extractor agent which uses Agent.run()."""
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        result = MagicMock()
        result.output = response
        return result
```

- [ ] **Step 2: Update `_make_engine` in `tests/test_debate_engine.py`**

Update the `_make_engine` function to include `_extractor_agent` and the import for `ArgumentSummary`:

Add to imports at top of `tests/test_debate_engine.py`:

```python
from models import ArgumentSummary
```

Add `_extractor_agent` line in `_make_engine`:

```python
def _make_engine(responses=None):
    """Create a DebateEngine with mocked agents."""
    import asyncio

    mock = MockDebateAgent(responses=responses)
    engine = object.__new__(DebateEngine)
    engine.model = "test:model"
    engine.base_url = None
    engine.api_key = None
    engine.brave_api_key = ""
    engine.debater_agent = mock
    engine.debater_agent_no_search = mock
    engine.judge_agent = MockDebateAgent(responses=responses or ["Judgment."])
    engine._extractor_agent = MockDebateAgent(responses=['{"points": ["mock claim"]}'])
    engine.state = None
    engine.event_queue = asyncio.Queue()
    engine._loop_task = None
    engine._history = {}
    return engine, mock
```

- [ ] **Step 3: Run all existing tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_debate_engine.py
git commit -m "test: add run method to MockDebateAgent and update _make_engine for extractor"
```

---

### Task 6: Add `_extract_key_points` method to DebateEngine

**Files:**
- Modify: `debate_engine.py`
- Test: `tests/test_debate_engine.py`

- [ ] **Step 1: Write the failing tests**

Add to end of `tests/test_debate_engine.py`:

```python
@pytest.mark.asyncio
async def test_extract_key_points_appends_summary():
    engine, _ = _make_engine()
    engine._extractor_agent = MockDebateAgent(responses=['{"points": ["Claim A", "Claim B"]}'])
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    await engine._extract_key_points("Alice", "Some argument text", 1)

    assert len(engine.state.argument_summaries) == 1
    summary = engine.state.argument_summaries[0]
    assert summary.round == 1
    assert summary.debater_name == "Alice"
    assert summary.points == ["Claim A", "Claim B"]


@pytest.mark.asyncio
async def test_extract_key_points_handles_json_error():
    engine, _ = _make_engine()
    engine._extractor_agent = MockDebateAgent(responses=['not valid json'])
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    await engine._extract_key_points("Alice", "Some text", 1)

    assert len(engine.state.argument_summaries) == 0


@pytest.mark.asyncio
async def test_extract_key_points_handles_empty_points():
    engine, _ = _make_engine()
    engine._extractor_agent = MockDebateAgent(responses=['{"points": []}'])
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])

    await engine._extract_key_points("Alice", "Some text", 1)

    assert len(engine.state.argument_summaries) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_debate_engine.py::test_extract_key_points_appends_summary -v`
Expected: FAIL with `AttributeError: 'DebateEngine' object has no attribute '_extract_key_points'`

- [ ] **Step 3: Write implementation**

Add import at top of `debate_engine.py`:

```python
from models import ArgumentSummary
```

Add `argument_summaries` field to `DebateState` dataclass:

```python
@dataclass
class DebateState:
    topic: str
    debaters: list[Debater]
    active: bool = True
    current_round: int = 0
    current_turn_index: int = 0
    history: list[Message] = field(default_factory=list)
    max_rounds: Optional[int] = None
    argument_summaries: list[ArgumentSummary] = field(default_factory=list)
```

Add `_extractor_agent` to `DebateEngine.__init__`:

```python
    def __init__(self, model: str, brave_api_key: str = "", base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.brave_api_key = brave_api_key
        self.debater_agent = create_debater_agent(model, base_url, api_key)
        self.debater_agent_no_search = create_debater_agent_no_search(model, base_url, api_key)
        self.judge_agent = create_judge_agent(model, base_url, api_key)
        self._extractor_agent = create_extractor_agent(model, base_url, api_key)
        self.state: Optional[DebateState] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._loop_task: Optional[asyncio.Task] = None
        self._history: dict[str, list[ModelMessage]] = {}
```

Update the import line in `debate_engine.py`:

```python
from agents import create_debater_agent, create_debater_agent_no_search, create_judge_agent, create_extractor_agent, DebaterDeps
```

Add `_extract_key_points` method to `DebateEngine` class, after the `resume` method:

```python
    async def _extract_key_points(self, debater_name: str, full_text: str, round_number: int):
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
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_debate_engine.py::test_extract_key_points_appends_summary tests/test_debate_engine.py::test_extract_key_points_handles_json_error tests/test_debate_engine.py::test_extract_key_points_handles_empty_points -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add debate_engine.py tests/test_debate_engine.py
git commit -m "feat: add _extract_key_points method and argument_summaries to DebateState"
```

---

### Task 7: Inject argument summaries into `_build_user_prompt`

**Files:**
- Modify: `debate_engine.py`
- Test: `tests/test_debate_engine.py`

- [ ] **Step 1: Write the failing tests**

Add to end of `tests/test_debate_engine.py`:

```python
def test_build_user_prompt_includes_summaries():
    engine, _ = _make_engine()
    skeptic = Debater(name="Skeptic", personality="Be skeptical.")
    optimist = Debater(name="Optimist", personality="Be optimistic.")
    engine.state = DebateState(
        topic="AI in education",
        debaters=[skeptic, optimist],
        history=[
            Message(speaker="Skeptic", content="Teachers need empathy."),
            Message(speaker="Optimist", content="AI can personalize."),
        ],
        argument_summaries=[
            ArgumentSummary(round=0, debater_name="Skeptic", points=["Teachers need empathy"]),
            ArgumentSummary(round=0, debater_name="Optimist", points=["AI can personalize learning"]),
        ],
    )

    prompt = engine._build_user_prompt(skeptic)

    assert "Key arguments" in prompt
    assert "Skeptic" in prompt
    assert "Teachers need empathy" in prompt
    assert "Optimist" in prompt
    assert "AI can personalize learning" in prompt


def test_build_user_prompt_no_summaries_when_empty():
    engine, _ = _make_engine()
    debater = Debater(name="Test", personality="Test.")
    engine.state = DebateState(
        topic="Test topic",
        debaters=[debater],
        history=[Message(speaker="Other", content="Hello")],
    )

    prompt = engine._build_user_prompt(debater)

    assert "Key arguments" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_debate_engine.py::test_build_user_prompt_includes_summaries -v`
Expected: FAIL — "Key arguments" not in prompt

- [ ] **Step 3: Write implementation**

Replace the `_build_user_prompt` method in `debate_engine.py`:

```python
    def _build_user_prompt(self, debater: Debater) -> str:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_debate_engine.py::test_build_user_prompt_includes_summaries tests/test_debate_engine.py::test_build_user_prompt_no_summaries_when_empty -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add debate_engine.py tests/test_debate_engine.py
git commit -m "feat: inject argument summaries into user prompt for cross-round memory"
```

---

### Task 8: Integrate extraction into `run_turn` and `update_model`

**Files:**
- Modify: `debate_engine.py`
- Test: `tests/test_debate_engine.py`

- [ ] **Step 1: Write the failing test**

Add to end of `tests/test_debate_engine.py`:

```python
@pytest.mark.asyncio
async def test_run_turn_calls_extract_key_points():
    engine, _ = _make_engine(responses=["My argument about AI."])
    extractor_mock = MockDebateAgent(responses=['{"points": ["AI transforms education"]}'])
    engine._extractor_agent = extractor_mock
    debater = Debater(name="Alice", personality="Test.")
    engine.state = DebateState(topic="Test", debaters=[debater])
    engine._history = {"Alice": []}

    await engine.run_turn()

    assert extractor_mock.call_count == 1
    assert extractor_mock.last_user_prompt is not None
    assert "Alice" in extractor_mock.last_user_prompt
    assert len(engine.state.argument_summaries) == 1
    assert engine.state.argument_summaries[0].debater_name == "Alice"
    assert engine.state.argument_summaries[0].points == ["AI transforms education"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_debate_engine.py::test_run_turn_calls_extract_key_points -v`
Expected: FAIL — extractor mock call_count is 0 (extraction not called yet)

- [ ] **Step 3: Write implementation**

In `debate_engine.py`, modify the `run_turn` method. After the line `self.state.history.append(Message(speaker=debater.name, content=full_text))` and the `debater_end` event emission, add the extraction call:

Find the section in `run_turn`:

```python
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
```

Replace with:

```python
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
```

Also update `update_model` to recreate the extractor agent. Find:

```python
    def update_model(self, model_name: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.debater_agent = create_debater_agent(model_name, base_url, api_key)
        self.debater_agent_no_search = create_debater_agent_no_search(model_name, base_url, api_key)
        self.judge_agent = create_judge_agent(model_name, base_url, api_key)
```

Replace with:

```python
    def update_model(self, model_name: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.debater_agent = create_debater_agent(model_name, base_url, api_key)
        self.debater_agent_no_search = create_debater_agent_no_search(model_name, base_url, api_key)
        self.judge_agent = create_judge_agent(model_name, base_url, api_key)
        self._extractor_agent = create_extractor_agent(model_name, base_url, api_key)
```

Also update `test_update_model_recreates_agents` in `tests/test_debate_engine.py` to also verify `_extractor_agent` recreation. Find the test and add a mock for `create_extractor_agent`:

```python
def test_update_model_recreates_agents():
    engine, _ = _make_engine()

    old_debater = engine.debater_agent
    old_judge = engine.judge_agent

    from unittest.mock import patch

    with patch("debate_engine.create_debater_agent") as mock_debater_creator, patch(
        "debate_engine.create_debater_agent_no_search"
    ) as mock_no_search_creator, patch(
        "debate_engine.create_judge_agent"
    ) as mock_judge_creator, patch(
        "debate_engine.create_extractor_agent"
    ) as mock_extractor_creator:
        mock_debater_creator.return_value = MockDebateAgent()
        mock_no_search_creator.return_value = MockDebateAgent()
        mock_judge_creator.return_value = MockDebateAgent()
        mock_extractor_creator.return_value = MockDebateAgent()

        engine.update_model("new:model", None, None)

        assert engine.model == "new:model"
        assert engine.debater_agent is not old_debater
        assert engine.judge_agent is not old_judge
        mock_debater_creator.assert_called_once_with("new:model", None, None)
        mock_no_search_creator.assert_called_once_with("new:model", None, None)
        mock_judge_creator.assert_called_once_with("new:model", None, None)
        mock_extractor_creator.assert_called_once_with("new:model", None, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add debate_engine.py tests/test_debate_engine.py
git commit -m "feat: integrate argument extraction into run_turn and update_model"
```

---

### Task 9: Frontend — concession markup regex in `renderContent`

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add concession markup replacement**

In `static/app.js`, find the `renderContent` method (around line 722). After the mention restoration block (after `return html.replace(/%%MENTION_(\d+)%%/g, ...)`), add concession replacement.

The current code at the return statement is:

```javascript
            return html.replace(/%%MENTION_(\d+)%%/g, (_, i) => {
                return `<span class="mention">${this.escapeHtml(mentions[parseInt(i)])}</span>`;
            });
```

Replace the entire return statement with:

```javascript
            let result = html.replace(/%%MENTION_(\d+)%%/g, (_, i) => {
                return `<span class="mention">${this.escapeHtml(mentions[parseInt(i)])}</span>`;
            });
            result = result.replace(/\[退让\]([\s\S]*?)\[\/退让\]/g, (_, text) => {
                return `<span class="concession">${text}</span>`;
            });
            return result;
```

- [ ] **Step 2: Verify manually**

Run: `python -m uvicorn main:app --reload --port 8000`

Start a debate and observe that if a debater uses `[退让]...[/退让]` markup, it renders with the concession class (CSS not yet styled, but the span will be in the DOM — verify via browser dev tools).

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: add concession markup regex replacement in renderContent"
```

---

### Task 10: Frontend — concession CSS styles

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Add concession styles**

Add after the `.message.system .message-content::after` block (around line 358), before the judge styles:

```css
/* Concession markup — tactical retreat styling */
.concession {
    display: inline;
    background: rgba(166, 115, 50, 0.06);
    border-left: 2px dashed var(--gold-dim);
    padding: 1px 6px 1px 8px;
    border-radius: 0 4px 4px 0;
    font-style: italic;
    color: var(--ink-soft);
}

.concession::before {
    content: '🤝 ';
    font-size: 0.85em;
    opacity: 0.7;
}
```

Add dark mode concession style after the existing `html.dark` block (after line 89):

```css
html.dark .concession {
    background: rgba(200, 150, 60, 0.08);
    border-left-color: var(--gold-dim);
    color: var(--ink-soft);
}
```

- [ ] **Step 2: Visual verification**

Start the server, begin a debate, and check that concession text (if produced by LLM) appears with:
- Soft background tint
- Dashed gold left border
- 🤝 icon prefix
- Italic text
- Correct appearance in both light and dark modes

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: add concession CSS styles with light/dark mode support"
```

---

### Task 11: Run full test suite and verify

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS, 0 failures

- [ ] **Step 2: Run server and smoke test**

Run: `python -m uvicorn main:app --reload --port 8000`

Verify:
1. Debaters load correctly
2. Debate starts and streams responses
3. No errors in server console
4. Frontend loads without JS errors

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address any issues from integration testing"
```

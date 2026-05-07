# Debater Intelligence Upgrade — Design Spec

**Date**: 2026-05-07
**Status**: Draft
**Scope**: Three features to make AI debaters behave more like skilled human debaters

## Background

Current debaters use static prompt templates in `agents.py`. Each debater:
- Generates responses independently per round
- Never concedes opposing points — always adversarial
- Uses the same rhetorical approach regardless of opponent style
- Lacks structured memory of earlier arguments, resulting in weak cross-round continuity

This makes debates feel like "sequential speeches" rather than genuine intellectual engagement.

## Features

### Feature 1: Strategic Concession

**Goal**: Debaters can honestly acknowledge strong opposing points on non-core issues, then pivot to stronger ground.

**Behavioral example**:
> **反方**: "正方说 AI 让教育更公平，但农村地区连网络都没有。"
> **正方**: "你说得对，数字鸿沟是个真实问题。[退让]我不否认基础设施的差距确实存在。[/退让]但换个角度看——正是远程教育技术的进步，才第一次让偏远地区的孩子接触到优质课程。"

**Implementation**:

1. **`agents.py`** — New constant `CONCESSION_INSTRUCTIONS`:
   - Injected from Round 2 onward (no conceding in opening statements)
   - Instructs debaters to use `[退让]...[/退让]` markup when conceding
   - Teaches when to concede (non-core positions where opponent has a valid point)
   - Teaches how to follow up (reframe the issue, pivot to a stronger argument)
   - Emphasizes concession is a tactical choice, not weakness

2. **`app.js`** — Post-markdown-rendering regex replacement:
   - Pattern: `\[退让\]([\s\S]*?)\[\/退让\]`
   - Replace with: `<span class="concession"><span class="concession-icon">🤝</span>$1</span>`

3. **`style.css`** — `.concession` class:
   - Soft background color (lighter shade of debater's color)
   - Dashed left border in debater's color
   - Subtle padding and border-radius
   - `.concession-icon` displayed inline, small size

**Files changed**: `agents.py`, `app.js`, `style.css`

### Feature 2: Dynamic Strategy Adaptation

**Goal**: Debaters analyze opponents' argumentation style and choose the most effective counter-strategy.

**Style-counterstrategy matrix** (encoded in prompt):

| Opponent style | Counter-strategy |
|---|---|
| Data/statistics heavy | Use human stories, emotional narratives, real-world examples |
| Emotional/storytelling | Counter with rigorous logic, statistics, systematic analysis |
| Aggressive/combative | Stay calm and measured; composure beats aggression |
| Cautious/measured | Seize initiative, push harder, force engagement |
| Abstract/theoretical | Ground the debate in concrete examples and practical consequences |

**Implementation**:

1. **`agents.py`** — New constant `STRATEGY_INSTRUCTIONS`:
   - Injected from Round 2 onward
   - Contains the style-counterstrategy matrix
   - Instructs debater to first observe opponent's style from previous messages, then choose the most effective response approach
   - Emphasizes adaptation should feel natural, not formulaic

2. **No code logic changes** — Pure prompt engineering

**Files changed**: `agents.py`

### Feature 3: Memory & Citation System (Intelligent Tier)

**Goal**: Debaters explicitly reference earlier arguments, creating narrative continuity and tracking unresolved points across rounds.

**Behavioral examples**:
- "你在第一轮说 X，但刚才又说 Y——这不矛盾吗？"
- "反方一直没有回应我关于 Z 的质疑，我再次请他正面回答。"
- "分析家第二轮提供的数据恰好支持了我的核心论点。"

**Implementation**:

1. **`models.py`** — New dataclass:
   ```python
   @dataclass
   class ArgumentSummary:
       round: int
       debater_name: str
       points: list[str]  # 2-3 key claims extracted from the debater's turn
   ```

2. **`agents.py`** — Two new constants:
   - `EXTRACT_POINTS_PROMPT`: System prompt for a lightweight LLM call that extracts key claims from a debater's response. Outputs JSON: `{"points": ["claim1", "claim2", "claim3"]}`
   - `MEMORY_INSTRUCTIONS`: Instructs debaters to reference specific earlier arguments, point out contradictions, track unanswered questions, and build on allies' points

3. **`debate_engine.py`** — Changes:
   - `DebateState` gets new field: `argument_summaries: list[ArgumentSummary] = field(default_factory=list)` — auto-initialized as empty list when DebateState is created in `start()`
   - In `run_turn`, after emitting `debater_end` event and before `_advance_turn()`, call `await _extract_key_points(debater.name, full_text, current_round)` which:
      - Runs a separate lightweight PydanticAI Agent (created once in `DebateEngine.__init__` as `self._extractor_agent`) with `EXTRACT_POINTS_PROMPT` as instructions and `output_type=str`
      - Sends the debater's full text as user prompt
      - Parses the JSON response `{"points": [...]}`
      - Appends `ArgumentSummary(round=current_round, debater_name=name, points=[...])` to `state.argument_summaries`
      - On any error (JSON parse failure, LLM error), silently returns without appending (non-blocking)
   - `_build_user_prompt` enhancement: when `state.argument_summaries` is non-empty, inject a formatted section before the message history:
     ```
     [Key arguments raised so far]:
     Round 1 - [Name]: claim1; claim2; claim3
     Round 2 - [Other Name]: claim1; claim2
     ```

4. **`_extractor_agent`** — New PydanticAI Agent instance on `DebateEngine`:
   - Created in `__init__` alongside existing agents
   - Uses same model/provider as debater agents
   - `deps_type=None`, `output_type=str`, no tools, no thinking
   - `instructions=EXTRACT_POINTS_PROMPT`
   - Recreated in `update_model()` alongside other agents

**Files changed**: `models.py`, `agents.py`, `debate_engine.py`

## Prompt Assembly Order

In `_build_debater_instructions`, the final parts order becomes:

1. Date context
2. `DEBATE_RULES` (existing)
3. `CONCESSION_INSTRUCTIONS` (new, Round 2+)
4. `STRATEGY_INSTRUCTIONS` (new, Round 2+)
5. `MEMORY_INSTRUCTIONS` (new, Round 2+)
6. Stance instruction
7. Personality
8. Search instructions (if enabled)
9. Round countdown

## Test Plan

### Feature 1 Tests
- Unit test: `_build_debater_instructions` includes `CONCESSION_INSTRUCTIONS` for Round 2+
- Unit test: `_build_debater_instructions` excludes `CONCESSION_INSTRUCTIONS` for Round 0
- Unit test: Frontend regex correctly replaces `[退让]...[/退让]` markup
- Unit test: Regex handles multi-line concession text
- Unit test: No false positives on partial matches

### Feature 2 Tests
- Unit test: `_build_debater_instructions` includes `STRATEGY_INSTRUCTIONS` for Round 2+
- Unit test: `_build_debater_instructions` excludes `STRATEGY_INSTRUCTIONS` for Round 0

### Feature 3 Tests
- Unit test: `ArgumentSummary` dataclass creation and field access
- Unit test: `_extract_key_points` parses valid JSON response correctly
- Unit test: `_extract_key_points` returns empty list on LLM error (graceful fallback)
- Unit test: `_build_user_prompt` includes "[Key arguments raised so far]" when summaries exist
- Unit test: `_build_user_prompt` omits summaries section when list is empty
- Unit test: `_build_user_prompt` summaries section is formatted correctly with debater names and claims

## Out of Scope

- No debate flow changes (no cross-examination rounds, no turn order changes)
- No SSE event type changes
- No persistence layer (argument summaries are in-memory, like all other state)
- No model selection UI changes
- No changes to judge behavior

## Risks

| Risk | Mitigation |
|---|---|
| LLM may not reliably use `[退让]` markup | Prompt must be very explicit; fallback: if markup rarely appears, the feature still works as behavioral guidance without UI feedback |
| Extra LLM call for point extraction adds latency | Use a short prompt and small max_tokens; extraction runs after turn completes (non-blocking for SSE stream) |
| Strategy instructions may make responses formulaic | Prompt must emphasize natural adaptation, not mechanical checklist |
| Prompt grows long with 3 new instruction blocks | Monitor total prompt length; keep each block concise (under 150 words) |

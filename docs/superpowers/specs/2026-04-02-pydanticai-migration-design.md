# PydanticAI Migration Design

Migrate the debate engine's LLM layer from raw OpenAI SDK to PydanticAI agents.

## Decisions

- **One Agent per debater role** — individual tool configurations per debater (future RAG/web search)
- **Native PydanticAI message format** (`ModelRequest`/`ModelResponse`)
- **Pure migration** — no new features, preserve all current behavior exactly
- **Keep OpenAI SDK** for `/api/models` endpoint only
- **Full Agent Native** approach — rewrite `debate_engine.py` to use PydanticAI as primary orchestration

## Architecture

### Current

```
main.py → DebateEngine → LLMClient (OpenAI SDK) → DeepSeek API
```

### Target

```
main.py → DebateEngine → DebaterAgent (PydanticAI Agent) → DeepSeek API
                      ↘ JudgeAgent  (PydanticAI Agent) → DeepSeek API
```

One shared `DebaterAgent` instance handles all debaters. Per-turn differences (personality, stance, round number) are injected via `DebaterDeps` and `instructions`. A separate `JudgeAgent` handles judging. Each debater maintains its own `message_history` in a dict keyed by name.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `agents.py` | **CREATE** | DebaterAgent + JudgeAgent factory functions, DebaterDeps dataclass |
| `debate_engine.py` | **REWRITE** | Use PydanticAI agents for LLM calls; keep state + SSE events |
| `main.py` | **UPDATE** | Remove LLMClient, add model string builder, update settings flow |
| `config.py` | **UPDATE** | Add `build_model_string()` helper |
| `llm_client.py` | **DELETE** | Replaced by PydanticAI agents |
| `models.py` | **UNCHANGED** | All Pydantic models stay the same |
| `presets.yaml` | **UNCHANGED** | Debater definitions stay the same |
| `tests/conftest.py` | **UPDATE** | Replace `MockLLMClient` with mock for PydanticAI agents |
| `tests/test_debate_engine.py` | **UPDATE** | Adapt to new engine API |
| `tests/test_llm_client.py` | **DELETE** | No longer relevant |
| `tests/test_main.py` | **UPDATE** | Adapt to new initialization |

## agents.py — Agent Definitions

### DebaterDeps

```python
@dataclass
class DebaterDeps:
    topic: str
    debater: Debater
    round_number: int
    max_rounds: int | None
```

Injected per-turn via `deps` parameter. Contains everything needed to build the system prompt dynamically.

### create_debater_agent(model: str) -> Agent[DebaterDeps, str]

Creates a PydanticAI Agent with:
- `instructions` function that builds the system prompt from `RunContext[DebaterDeps]`
- The function composes: DEBATE_RULES + stance instruction + personality + round countdown
- Identical prompt content to current `build_messages()` system prompt
- `output_type=str` (plain text output, same as current)
- No tools yet (future: RAG, web search)

### create_judge_agent(model: str) -> Agent[None, str]

Creates a PydanticAI Agent with:
- Static `instructions` containing the judge prompt (identical to current)
- No deps needed (judge receives full transcript as user prompt)
- `output_type=str`

### Prompt composition (instructions function)

The `@agent.instructions` decorator function produces the same system prompt as the current `build_messages()` method, including:
1. DEBATE_RULES (shared rules)
2. STANCE_INSTRUCTIONS[stance] (role-specific focus)
3. debater.personality (unique persona from presets.yaml)
4. Round countdown (when max_rounds is set)

## debate_engine.py — Core Rewrite

### State management — UNCHANGED

- `DebateState` dataclass: topic, debaters, active, current_round, current_turn_index, history, max_rounds
- `Message` dataclass: speaker, content, timestamp
- `Event` dataclass: type, payload
- `start()`, `stop()`, `resume()`, `inject_message()` — same signatures and behavior

### New: Per-debater message history

```python
self._history: dict[str, list[ModelMessage]] = {}
```

Each debater gets its own PydanticAI `message_history` list. This is separate from the shared `self.state.history` (which remains the canonical `Message` list).

### run_turn() — rewritten

1. Build `DebaterDeps` for current debater
2. Build `user_prompt` string from shared history (other debaters' messages + topic)
3. Emit `debater_start` event
4. Call `self.debater_agent.run_stream(user_prompt, deps=deps, message_history=self._history[debater.name])`
5. Stream deltas via `result.stream_text(delta=True)`, emit `debater_chunk` events
6. After stream completes, update `self._history[debater.name] = result.all_messages()`
7. Add `Message` to shared history
8. Emit `debater_end` event
9. Advance turn

### _build_user_prompt(debater) — replaces build_messages()

First turn (empty history):
```
"You are the first speaker. No one has spoken yet — do NOT reference or quote anyone. Present your opening argument on the topic: {topic}"
```

Subsequent turns:
```
"Debate topic: {topic}\n\n[Speaker1]: content\n\n[Speaker2]: content\n\n..."
```

Own messages are excluded — they're already in `message_history` as `ModelResponse` entries.

### judge() — rewritten

1. Build transcript string from shared history (all messages, including user)
2. Call `self.judge_agent.run_stream(transcript)`
3. Stream deltas, emit `judge_chunk` events
4. Emit `judge_result` event

### update_model(model: str) — new method

Recreates both agents when API settings change (called from `/api/settings` endpoint).

### run_loop() — UNCHANGED

The outer loop logic (round tracking, stop/resume, max rounds check) remains identical.

## main.py — Updated Initialization

### Changes

- Remove `from llm_client import LLMClient`
- Remove `from openai import AsyncOpenAI` (keep only for `/api/models`)
- In `lifespan()`: create `DebateEngine(model=build_model_string(...))`
- In `/api/settings`: call `debate_engine.update_model(model_string)`
- Keep `AsyncOpenAI` import and `/api/models` endpoint AS-IS

### /api/models — UNCHANGED

Still uses `AsyncOpenAI` directly. This is the only remaining use of the OpenAI SDK for chat.

## config.py — Model String Builder

Add `build_model_string(base_url: str, model: str) -> str`:

- `api.deepseek.com` → `"deepseek:deepseek-chat"`
- `api.openai.com` → `"openai:gpt-4o"`
- Unknown host → `"openai:{model}"` with a note that custom providers need extra config

When the model string doesn't match a known provider, the factory functions in `agents.py` use `OpenAIChatModel` with `OpenAIProvider(base_url=base_url, api_key=api_key)`. The `create_debater_agent()` and `create_judge_agent()` functions accept an optional `provider_config: dict` parameter with `base_url` and `api_key` for this fallback path.

## Dependencies

- **ADD**: `pydantic-ai>=1.0.0`
- **KEEP**: `openai>=1.12.0` (for `/api/models` only)
- All other dependencies unchanged

## Tests

### conftest.py

Replace `MockLLMClient` with `MockDebateAgent` that mimics PydanticAI's `run_stream` return type:

- Returns an async context manager
- `stream_text(delta=True)` yields words one at a time
- `all_messages()` returns an empty list (tests don't need real history)
- Stores `call_count` and `last_user_prompt` for assertions

### test_debate_engine.py

- Update to use `MockDebateAgent` instead of `MockLLMClient`
- Tests for message building become tests for `_build_user_prompt()`
- All existing test cases (turn order, round end, max rounds, stop/resume) remain valid
- Constructor changes from `DebateEngine(llm_client=...)` to `DebateEngine(model="test")`

### test_llm_client.py

Delete. No longer relevant.

### test_main.py

- Update initialization to match new `DebateEngine` constructor
- Keep existing test for `/api/models` (still uses OpenAI SDK)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| PydanticAI stream delta cadence differs from raw OpenAI chunks | Frontend may receive chunks at different granularity | Test with real API; `stream_text(delta=True)` should produce similar behavior |
| Custom OpenAI-compatible providers need extra config | Users of non-DeepSeek providers may need code changes | Provide fallback via `OpenAIProvider(base_url=...)` in agents.py |
| Per-debater message_history grows unbounded | Token limits on long debates | Add `history_processors` to trim old messages (future, not in scope) |
| Two SDKs in requirements (pydantic-ai + openai) | Slightly larger dependency footprint | Accepted trade-off for `/api/models` functionality |

## Out of Scope

- RAG tool implementation (future)
- Web search tool implementation (future)
- Per-debater custom tools (future)
- History processors / summarization (future)
- Multi-user support (not planned)
- Frontend changes (API contract unchanged)

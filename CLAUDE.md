# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the server
python -m uvicorn main:app --reload --port 8000

# Or use the startup script (installs deps + starts server)
./start.sh [port]

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_debate_engine.py -v

# Run single test
python -m pytest tests/test_debate_engine.py::test_build_messages_assigns_correct_roles -v
```

## Architecture

### PydanticAI Agent Layer

The LLM layer uses **PydanticAI Agents** (not raw OpenAI SDK). Defined in `app/agents.py`:

- **`create_debater_agent(enable_search=...)`** — debater agent (thinking always on; `web_search` tool registered only when `enable_search=True`)
- **`create_judge_agent()`** — judge agent, no tools, no thinking
- **`create_extractor_agent()`** — lightweight agent extracting key claims per turn (for cross-round memory)

Each agent uses `DebaterDeps` for dependency injection (topic, debater config, round number, Brave API key). The `instructions` callback (`_build_debater_instructions`) rebuilds the system prompt fresh on every run, composing: date context → `DEBATE_RULES` → stance instruction → personality → `SEARCH_INSTRUCTIONS` (if search enabled) → round countdown.

### Core Algorithm: Prompt Building

In `app/engine/debate.py:_build_user_prompt()`, for each debater's turn:

- **Other** debaters' messages → `[Name]: content` in the user prompt
- Debater's **own** past messages → excluded from user prompt (already in `message_history` as prior `ModelResponse` entries managed by PydanticAI)
- **First turn** (empty history) → opening-statement prompt instead of debate history

### Data Flow

```
User starts debate → routes/debate.py:start_debate (Depends(get_engine))
  → engine.start(topic, debaters)
  → SSE consumer connects → engine.ensure_loop_running()
  → asyncio.create_task(engine._run_loop_and_cleanup())
  → run_loop() calls run_turn() for each debater in round-robin
  → run_turn() calls agent.run_stream_events(), streams response, emits SSE events
  → Frontend receives SSE events, updates DOM in real-time
```

### SSE Events

Events are the `Event` dataclass in `app/engine/state.py`, emitted to `event_queue`. The SSE endpoint at `/api/debate/stream` (`app/routes/debate.py`) yields `event: <type>\ndata: <json>\n\n`.

Full event types: `debater_start`, `thinking_chunk`, `debater_finalize`, `debater_chunk`, `debater_end`, `tool_call`, `round_end`, `debate_end`, `debate_paused`, `judge_chunk`, `judge_result`, plus the failure-terminal `debate_error` / `judge_error`.

The SSE stream calls `ensure_loop_running()` **after** the consumer connects. Stream terminates on any terminal event (`TERMINAL_EVENTS` in `app/routes/debate.py`): `debate_end`, `judge_result`, `debate_paused`, `debate_error`, `judge_error`. A 30-second keepalive prevents connection timeouts.

### Web Search

`app/tools.py` provides a `web_search` function (Brave Search API) with a 1 req/sec rate limiter (`_RateLimiter`). It's registered as a PydanticAI tool on the search-enabled debater agent. The `SEARCH_INSTRUCTIONS` in `app/agents.py` enforce a two-phase strategy: Round 1 is knowledge gathering (multiple searches), Round 2+ is conservation mode (max 1 search/round, only for verifiable claims).

### Global State

Application state lives on `app.state` (FastAPI's standard `State`), populated
during lifespan in `create_app()`: `engine` (`DebateEngine`),
`debater_repository` (`DebaterRepository`, in-memory custom debaters behind an
`asyncio.Lock`), and `index_html` (cached). Routes access these via `Depends`
providers in `app/deps.py` (`get_engine`, `get_debater_repository`) rather than
module-level globals. Intentional single-user, in-memory only — no multi-user
or persistence support.

## Key Files

The backend is organised as an `app/` package; `main.py` is a thin shim (`app = create_app()`).

| File | Purpose |
|------|---------|
| `app/engine/debate.py` | Core logic: state, prompt building, turn order, SSE event emission |
| `app/engine/state.py` | `Message` / `DebateState` / `Event` dataclasses (stdlib-only) |
| `app/agents.py` | PydanticAI agent definitions, prompt templates (`DEBATE_RULES`, `STANCE_INSTRUCTIONS`, `SEARCH_INSTRUCTIONS`, `JUDGE_PROMPT`), `DebaterDeps` |
| `app/tools.py` | `web_search` PydanticAI tool with Brave Search API + rate limiting |
| `app/routes/*.py` | FastAPI routers (debate / debaters / topic), dependencies via `Depends` |
| `app/deps.py` | `get_engine` / `get_debater_repository` providers + `DebaterRepository` |
| `app/__init__.py` | `create_app()` factory: lifespan, static mount, router registration |
| `app/presets.yaml` | Pre-defined debater personas (Chinese) |
| `app/config.py` | Pydantic Settings (from `.env`) + cached `load_presets()` |
| `app/models.py` | Pydantic models for API contracts + input length validation |

## Frontend

Single-page app in `static/` using vanilla JS (`DebateApp` class in `app.js`). Key patterns:
- **Language**: UI text and preset debaters are in Chinese (`lang="zh-CN"`)
- SSE connection handles all event types including `thinking_chunk` and `tool_call`
- Thinking sections use CSS Grid collapse for smooth fold animations
- UI state machine: `idle` → `debating` → `paused`/`stopped`
- Debaters are draggable to set turn order
- `marked.js` renders Markdown; `[[Name]]` patterns become highlighted mention badges
- Download exports the chat as a self-contained HTML file
- Auto-triggers judge when debate ends naturally (max rounds reached)

## Configuration

Loaded from `.env` via **Pydantic Settings** (`app/config.py:Settings`, `BaseSettings` with `env_file`). Defaults are baked into the field declarations:

| Variable | Default | Purpose |
|----------|---------|---------|
| `API_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible endpoint |
| `API_KEY` | _(empty)_ | LLM provider API key |
| `MODEL` | `deepseek-reasoner` | Model name |
| `BRAVE_API_KEY` | _(empty)_ | Brave Search API key (optional) |

Works with any OpenAI-compatible API (DeepSeek, Ollama, vLLM, LM Studio, OpenAI).

## Preset Debaters

Defined in `presets.yaml`. Stance values are Chinese: `正方`/`反方`/`中立`.

| Name | Avatar | Stance | Search | Style |
|------|--------|--------|--------|-------|
| 正方 | 🟢 | 正方 | Yes | Passionate advocate, cites success stories |
| 反方 | 🔴 | 反方 | Yes | Sharp critic, finds logical flaws |
| 分析家 | 🔵 | 中立 | No | Data-driven, weighs multiple perspectives |

### Adding a New Preset Debater

Edit `presets.yaml`:

```yaml
debaters:
  - name: "实用主义者"
    color: "#9b59b6"
    avatar: "🟣"
    stance: "中立"
    enable_search: true
    personality: |
      你是"实用主义者"——一位注重实际解决方案的思考者。
      你关注成本、收益和现实世界中的可行性。
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve `static/index.html` |
| GET | `/api/presets` | Return preset debaters |
| GET | `/api/debaters` | Return presets + custom debaters |
| POST | `/api/debate/start` | Start debate (2+ debaters required) |
| GET | `/api/debate/stream` | SSE event stream |
| POST | `/api/debate/message` | Inject user message |
| POST | `/api/debate/stop` | Pause debate |
| POST | `/api/debate/resume` | Resume debate |
| POST | `/api/debate/judge` | Request judgment (debate must be stopped) |
| POST | `/api/debaters` | Create custom debater (no duplicate names) |
| POST | `/api/topic/refine` | AI-powered topic refinement |

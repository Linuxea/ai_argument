# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the server
python -m uvicorn main:app --reload --port 8000

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_debate_engine.py -v

# Run single test
python -m pytest tests/test_debate_engine.py::test_build_messages_assigns_correct_roles -v
```

### Known Test Failures

Two tests fail because `presets.yaml` uses Chinese names but assertions expect English:
- `tests/test_config.py::test_load_presets_returns_list_of_debaters` — expects "The Skeptic", actual "质疑者"
- `tests/test_main.py::test_get_presets_returns_debaters` — same issue

Fix: update test assertions to match the Chinese preset names, or restore English presets.

## Architecture

### Core Algorithm: Message Role Mapping

The key algorithm is in `debate_engine.py:build_messages()`. When building the message array for a debater's API call:

- Debater's **own** past messages → `role: "assistant"`
- **Other** debaters' messages → `role: "user"` with `[Name]:` prefix
- User messages → `role: "user"` with `[You]:` prefix

For the **first turn** (empty history), a special opening-statement prompt is injected instead of the debate history. The system prompt also includes a **round countdown** ("This is round X of Y") when `max_rounds` is set.

### Debater Prompts

Each debater's system prompt is composed of three parts:
1. `DEBATE_RULES` — shared rules: 80–200 words, `[[Name]]` mentions, no headers/labels, rebuttals must advance own argument
2. `STANCE_INSTRUCTIONS[stance]` — role-specific focus: "for" attacks opponents, "against" finds flaws, "neutral" weighs both sides
3. `debater.personality` — unique persona from `presets.yaml` or custom debater config

### Data Flow

```
User starts debate → main.py:start_debate()
  → debate_engine.start(topic, debaters)
  → SSE consumer connects → debate_engine.ensure_loop_running()
  → asyncio.create_task(debate_engine.run_loop())
  → run_loop() calls run_turn() for each debater in round-robin
  → run_turn() builds messages, streams LLM response, emits SSE events
  → Frontend receives SSE events, updates DOM in real-time
```

### SSE Events

Events are defined in `debate_engine.py` as the `Event` dataclass and emitted to `event_queue`. The SSE endpoint at `/api/debate/stream` yields these as `event: <type>\ndata: <json>\n\n`.

Event types: `debater_start`, `debater_chunk`, `debater_end`, `round_end`, `debate_end`, `judge_chunk`, `judge_result`

The SSE stream calls `ensure_loop_running()` **after** the consumer connects to prevent early events from being lost. Stream terminates on `debate_end` or `judge_result`. A 30-second keepalive (`: keepalive\n\n`) prevents connection timeouts.

### Global State

The app uses module-level globals (`debate_engine`, `custom_debaters`) in `main.py`. This is intentional for a single-user personal tool but means no multi-user support.

## Key Files

| File | Purpose |
|------|---------|
| `debate_engine.py` | Core logic: state, message building, turn order, SSE events, judge |
| `main.py` | FastAPI routes, SSE endpoint, lifespan management |
| `llm_client.py` | Thin wrapper around OpenAI SDK with streaming |
| `presets.yaml` | Pre-defined debater personas (Chinese) |
| `config.py` | Settings class (DeepSeek defaults), loads presets from YAML |
| `models.py` | Pydantic models for API contracts |

## Frontend

Single-page app in `static/` using vanilla JS (`DebateApp` class in `app.js`). Key patterns:
- **Language**: UI text and preset debaters are in Chinese (`lang="zh-CN"`)
- SSE connection handles all event types and renders them in real-time
- UI state machine: `idle` → `debating` → `paused`/`stopped` (controls button enable/disable)
- Debaters are draggable to set turn order
- `marked.js` renders Markdown; `[[Name]]` patterns in messages become highlighted mention badges
- Settings sync bidirectionally: localStorage ↔ backend API
- Download exports the chat as a self-contained HTML file
- Auto-triggers judge when debate ends naturally (max rounds reached)

## Configuration

Defaults to DeepSeek (`https://api.deepseek.com`, model `deepseek-chat`, env var `DEEPSEEK_API_KEY`). Works with any OpenAI-compatible API. Change via:
- UI sidebar (URL, API key, model dropdown with auto-discovery)
- `DEEPSEEK_API_KEY` environment variable
- `config.py:Settings` class defaults

## Preset Debaters

Defined in `presets.yaml` with Chinese names and personality descriptions:

| Name | Avatar | Stance | Style |
|------|--------|--------|-------|
| 质疑者 | 🔴 | against | Sharp critic, finds logical flaws and weak evidence |
| 乐观派 | 🟢 | for | Passionate advocate, cites success stories and precedents |
| 分析家 | 🔵 | neutral | Data-driven, weighs multiple perspectives, spots false dichotomies |

## Adding a New Preset Debater

Edit `presets.yaml`:

```yaml
debaters:
  - name: "实用主义者"
    color: "#9b59b6"
    avatar: "🟣"
    stance: "neutral"
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
| GET | `/api/models` | List models from API provider |
| POST | `/api/settings` | Update API settings |
| POST | `/api/debaters` | Create custom debater (no duplicate names) |

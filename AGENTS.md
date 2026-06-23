# AGENTS.md

Operational cheat sheet for OpenCode sessions. Covers the full architecture (PydanticAI agents, SSE event flow, prompt building, data flow diagrams) plus what an agent would likely get wrong without help.

## Commands

```bash
# Backend (Python 3.10+, .venv/)
.venv/bin/python -m pytest tests/ -v                                                 # all tests
.venv/bin/python -m pytest tests/test_bug_fixes.py -v                                # one file
.venv/bin/python -m pytest tests/test_debate_engine.py::test_start_raises_error_on_empty_debaters -v  # one test
.venv/bin/python -m pytest tests/ --cov=app --cov-report=term-missing                # coverage

# Frontend (Node 22+, vanilla ES modules, no build step)
npm test                                                                             # node --test 'tests-js/*.test.js'
node --test tests-js/renderer.test.js                                                # one file

# Run server
python -m uvicorn main:app --reload --port 8000
./start.sh [port]                                                                    # also runs pip install -r
```

Backend and frontend are **two independent test suites with no shared runner**. Run both before declaring work done.

## Architecture

### PydanticAI Agent Layer

The LLM layer uses **PydanticAI Agents** (not raw OpenAI SDK, except `app/routes/topic.py` which intentionally does a one-shot topic-refine via `AsyncOpenAI`). Defined in `app/agents.py`:

- **`create_debater_agent(enable_search=...)`** — debater agent (thinking always on; `web_search` tool registered only when `enable_search=True`)
- **`create_judge_agent()`** — judge agent, no tools, no thinking
- **`create_extractor_agent()`** — lightweight agent extracting key claims per turn (for cross-round memory)

Each agent uses `DebaterDeps` for dependency injection (topic, debater config, round number, Brave API key). The `instructions` callback (`_build_debater_instructions`) rebuilds the system prompt fresh on every run, composing: date context → `DEBATE_RULES` → (round ≥ 1: `STRATEGY_INSTRUCTIONS` + `MEMORY_INSTRUCTIONS`) → stance → personality → `SEARCH_INSTRUCTIONS` (if search enabled) → round countdown. **Personality is framed as HIGHEST-priority voice/tone** and explicitly overrides the generic "be professional / back up claims" style rules in `DEBATE_RULES` — without this framing, playful/contrarian characters get suppressed. Don't "tidy" that framing away.

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

Events are the `Event` dataclass in `app/engine/state.py`, emitted to `event_queue` via `engine._emit(Event(...))` (which assigns the monotonic id and appends to the 500-event replay buffer that powers `Last-Event-ID` reconnect). The SSE endpoint at `/api/debate/stream` (`app/routes/debate.py`) yields `event: <type>\ndata: <json>\n\n`.

Full event types: `debater_start`, `thinking_chunk`, `debater_finalize`, `debater_chunk`, `debater_end`, `tool_call`, `round_end`, `debate_end`, `debate_paused`, `judge_chunk`, `judge_result`, plus the failure-terminal `debate_error` / `judge_error`.

The SSE stream calls `ensure_loop_running()` **after** the consumer connects. Stream terminates on any terminal event (`TERMINAL_EVENTS` in `app/routes/debate.py`): `debate_end`, `judge_result`, `debate_paused`, `debate_error`, `judge_error`. A 30-second keepalive prevents connection timeouts.

### Web Search

`app/tools.py` provides a `web_search` function (Brave Search API) with a 1 req/sec rate limiter (`_RateLimiter`). It's registered as a PydanticAI tool on the search-enabled debater agent. The `SEARCH_INSTRUCTIONS` in `app/agents.py` enforce a two-phase strategy: Round 1 is knowledge gathering (multiple searches), Round 2+ is conservation mode (max 1 search/round, only for verifiable claims).

**Per-debater `enable_search`** lives on `Debater` (default True; presets can disable, e.g. 分析家). The start route (`/api/debate/start`) also takes a global **`DebateConfig.search_enabled` kill-switch** (default True): when False it `model_copy`s every selected debater to `enable_search=False`. **Kill-switch semantics: it only disables — turning it ON never grants search to a debater whose preset disables it.** Don't "fix" this into a hard override.

### Global State

Application state lives on `app.state` (FastAPI's standard `State`), populated during lifespan in `create_app()`: `engine` (`DebateEngine`), `debater_repository` (`DebaterRepository`, in-memory custom debaters behind an `asyncio.Lock`), and `index_html` (cached). Routes access these via `Depends` providers in `app/deps.py` (`get_engine`, `get_debater_repository`) rather than module-level globals. Intentional single-user, in-memory only — no multi-user or persistence support.

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

## Frontend layout

Single-page app in `static/` using vanilla ES modules (no bundler, no framework, no JSX). Loaded via `<script type="module">` in `index.html`. **Deps vendored locally** in `static/vendor/`: `marked@12.0.2` (markdown) + `lucide@0.469.0` (icons), loaded via `<script defer>` (the **marked version is a deliberate security pin** — marked has had XSS regressions; don't bump without checking). `markdown.js`/`utils.js` still degrade gracefully if the globals are missing (only hit in tests). To update a vendored lib, download from the Aliyun mirror into `static/vendor/` and bump the `?v=` cache-bust in `index.html`.

```
static/
├── index.html              # App shell, sidebar, chat area, search <dialog>
├── app.js                  # DebateApp orchestrator: wiring, SSE dispatcher, state machine
├── favicon.svg
├── modules/                # ES modules
│   ├── api.js              # fetch calls + FastAPI error-format flattening
│   ├── sse.js              # SSEClient extends EventSource wrapper
│   ├── state.js            # UIState FSM (idle/debating/paused/stopped/judging)
│   ├── markdown.js         # marked config + [[Name]] mention decoration
│   ├── renderer.js         # streaming bubbles, thinking section, tool cards, judge turn
│   ├── autoscroll.js       # sentinel + IntersectionObserver + floating jump button
│   ├── debaters.js         # debater list render, HTML5 drag reorder, keyboard reorder
│   ├── search.js           # <dialog> search with highlight + jump
│   ├── theme.js            # light/dark + View Transitions API
│   ├── toast.js            # capped notification stack
│   └── utils.js            # escapeHtml, sanitizeColor, debounce, icon, refreshIcons
└── styles/                 # cascade layers
    ├── main.css            # layer order + @import hub
    ├── tokens.css          # design tokens, dark theme, reduced-motion
    ├── base.css            # reset, scrollbar, focus ring
    ├── layout.css          # sidebar/chat shell + responsive breakpoint
    ├── components.css      # buttons, inputs, debater items, toasts
    ├── messages.css        # bubbles, skeleton, cursor, mentions, judge accent
    └── search.css          # search drawer
```

Key frontend patterns:
- **Language**: UI text and preset debaters are in Chinese (`lang="zh-CN"`)
- SSE connection handles all event types including `thinking_chunk` and `tool_call`
- **`[[Name]]` is the ONLY custom markup the model is asked to emit** (`DEBATE_RULES`), and the only custom markup `markdown.js` detects → `<span class="mention">` badge. A `[退让]…[/退让]` concession feature existed and was removed: it depended on the model reliably emitting paired tags (it didn't), and its second `marked.parse` pass re-escaped mention spans and leaked literal tag text. **Do not re-introduce paired/closing custom markup the model must produce** — it's fragile. Plain `[[Name]]` (no closing tag) is the tolerable edge.
- **Mention rendering order matters**: `[[Name]]` → `\u0000MENTION_N\u0000` placeholder *before* `marked.parse`, expanded to `<span class="mention">` only *after* all parsing. Pre-expanding lets marked's `renderer.html` (raw-HTML escape) eat the span. `markdown.test.js`'s stub replicates that escaping so it catches this regression.
- Thinking sections + tool-card results **default to EXPANDED** (`finalize()` no longer collapses thinking; tool cards don't start with `tool-card-collapsed`). The header toggle still collapses manually. Don't "fix" these back to collapsed-by-default.
- Per-debater bubble tint: `renderer.js` sets `--bubble-color` on each `.message.ai`; `messages.css` uses `color-mix(in srgb, var(--bubble-color) 8%, var(--bg-elevated))`. Degrades gracefully (declaration dropped on browsers without `color-mix`).
- Thinking sections use CSS Grid collapse for the fold animation; the tool-card fold uses the same `grid-template-rows: 0fr` trick. Note: the collapsing grid item must have **no vertical padding** (padding blocks the `0fr` fold and leaks a background sliver) — vertical padding lives on its first/last children instead.
- UI state machine: `idle` → `debating` → `paused`/`stopped`
- Debaters are draggable to set turn order (HTML5 DnD; **mobile/touch not supported**)
- Download exports the chat as a self-contained HTML file
- Auto-triggers judge when debate ends naturally (max rounds reached); the 5-second countdown toast auto-dismisses when the timer fires

## Test conventions (non-obvious)

- **Backend coverage is at 100% and enforced** by `pyproject.toml`'s `[tool.pytest.ini_options]` (`--cov-fail-under=100`). Any new code path in `app/` needs a test. Don't add `# pragma: no cover` casually.
- **Bug-fix tests live in `tests/test_bug_fixes.py`** named `test_bN_<topic>` where N matches the audit ID. The historical audit covers B1–B32, but **11 IDs (B13, B14, B17, B23, B24, B26–B29, B31, B32) have no regression test** — they were either merged into other tests or never independently fixed. When fixing a regression, continue the `test_bN_*` convention.
- **Engine tests build via `object.__new__(DebateEngine)` + manual attribute init**, NOT via `__init__` (which constructs real PydanticAI agents needing API keys). There is a **single shared helper `_make_engine()` in `tests/conftest.py`** — when you add an attribute to `DebateEngine`, update it (previously two helpers existed; they were consolidated).
- **Frontend tests use jsdom** with central stubs in `tests-js/helpers/jsdom-env.js` for `matchMedia`, `CSS.escape`, `IntersectionObserver`, and `HTMLDialogElement.showModal`. `EventSource` is stubbed per-test-file (`tests-js/sse.test.js`) because it carries test-specific behavior. Every test file must call `setupDom()` before importing from `static/`.
- **marked and lucide are vendored but absent in tests.** Each frontend test file defines its own inline `globalThis.window.marked = {…}` stub (there is **no shared stub file** despite old docs claiming `tests-js/helpers/marked-stub.js`). `markdown.js` degrades to plain-text without `window.marked`; `utils.refreshIcons()` is a no-op without `window.lucide`. The `markdown.test.js` stub is the faithful one — it runs raw HTML through a `renderer.html` override the way real marked does, so it catches XSS/escape regressions; mirror that behaviour when adding markdown tests.
- `asyncio_mode = "auto"` in `pyproject.toml` — async tests don't need `@pytest.mark.asyncio` (adding it is harmless).

## Constraints an agent would miss

- **`app.state.engine` is `None` until FastAPI lifespan runs.** Use `with TestClient(app):` so startup fires, or override via `app.dependency_overrides[get_engine] = lambda: fake`. Without this, every debate route returns 503 "Service not ready".
- **`/api/debate/start` returns 409 if a debate is already active.** This is intentional — silently clobbering state orphans the existing SSE consumer. Don't "fix" the 409.
- **`/api/debate/stream` enforces single-consumer** — a second concurrent stream returns 409. The replay buffer (`Last-Event-ID`) handles reconnect of the *same* consumer; it is not a fan-out bus.
- **`stop()` cancels `_loop_task` to interrupt the in-flight turn.** It's a sync method by design (called from a sync route handler). Don't make it await-able.
- **All engine SSE emissions go through `engine._emit(Event(...))`**, not direct `event_queue.put`. `_emit` assigns the monotonic id and appends to the 500-event replay buffer that powers `Last-Event-ID` reconnect. **Terminal error events also go through `_emit`** so that a reconnecting client sees them on replay.
- **Single-user, in-memory, no persistence, no auth.** Don't add user-scoping, DB layers, or auth unless the product actually changes.
- **LLM layer is PydanticAI Agents** (`app/agents.py`). `app/routes/topic.py` currently does a one-shot topic-refine via raw `AsyncOpenAI`; the plan is to migrate it to a PydanticAI agent too.
- **Frontend is vanilla JS ES modules** — no bundler, no JSX, no framework. `static/index.html` loads everything via `<script type="module">`. Don't introduce a build step lightly.
- **Stance values are Chinese literals** (`正方` / `反方` / `中立`), centralised as `app/models.Stance = Literal[...]` and reused by `STANCE_INSTRUCTIONS`. UI text and presets are in Chinese; match this when adding strings.
- **Presets live in `app/presets.yaml`**, loaded once via `lru_cache` and validated fail-fast at lifespan startup. Editing the YAML changes preset debaters without code changes — no migration needed.

## Environment quirks

- **No direct PyPI / npm access in this environment.** Use mirrors:
  ```bash
  .venv/bin/pip install --index-url https://mirrors.aliyun.com/pypi/simple <pkg>
  npm install --registry https://registry.npmmirror.com <pkg>
  ```
- `.env` is gitignored but expected at repo root (`API_KEY`, `MODEL`, `BRAVE_API_KEY`, `API_BASE_URL`). Defaults baked into `app/config.py:Settings`.
- Dependencies are pinned in `requirements.txt` (compatible-release `~=`); regenerate with `uv pip compile` when adding deps.
- No CI, no pre-commit hooks, no PR template. Commits push directly to `main`. Linting is `ruff` (`pyproject.toml` config), run it before committing.

## Workflow conventions

- **Don't add inline comments unless asked.** The codebase style is minimal comments. Docstrings on public functions/classes are welcome; line-by-line narration of what code does is not.
- **Don't commit or push unless explicitly asked.**
- **Bug-fix commit messages** use `fix: <summary>` with a body listing each bug ID. Refactors use `refactor(scope): ...`. Match this style.

# AGENTS.md

Operational cheat sheet for OpenCode sessions. **Read `CLAUDE.md` first** — it has the full architecture (PydanticAI agents, SSE event flow, prompt building, data flow diagrams). This file covers only what an agent would likely get wrong without help.

## Commands

```bash
# Backend (Python 3.14, .venv/)
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

## Test conventions (non-obvious)

- **Backend coverage is at 100% and expected to stay there.** Any new code path in `app/` needs a test. Don't add `# pragma: no cover` casually.
- **Bug-fix tests live in `tests/test_bug_fixes.py`** named `test_bN_<topic>` where N matches the audit ID. Continue this convention when fixing regressions — the B1–B32 ids are referenced in commit messages and code comments.
- **Engine tests build via `object.__new__(DebateEngine)` + manual attribute init**, NOT via `__init__` (which constructs real PydanticAI agents needing API keys). Two helpers exist: `_make_engine()` in `tests/test_debate_engine.py` and `_bare_engine()` in `tests/test_coverage_extras.py`. **When you add an attribute to `DebateEngine`, update both helpers** or every engine test will `AttributeError`.
- **Frontend tests use jsdom** with stubs for `matchMedia`, `CSS.escape`, `IntersectionObserver`, `HTMLDialogElement`, and `EventSource` in `tests-js/helpers/jsdom-env.js`. Every test file must call `setupDom()` before importing from `static/`.
- **marked and lucide are CDN-only** and absent in tests. `markdown.js` degrades to plain-text; `utils.refreshIcons()` is a no-op without `window.lucide`. Stub them per-test if you need real output.
- `asyncio_mode = "auto"` in `pyproject.toml` — async tests don't need `@pytest.mark.asyncio` (adding it is harmless).

## Constraints an agent would miss

- **`app.state.engine` is `None` until FastAPI lifespan runs.** Use `with TestClient(app):` so startup fires, or override via `app.dependency_overrides[get_engine] = lambda: fake`. Without this, every debate route returns 400 "Service not ready".
- **`/api/debate/start` returns 409 if a debate is already active.** This is intentional — silently clobbering state orphans the existing SSE consumer. Don't "fix" the 409.
- **`stop()` cancels `_loop_task` to interrupt the in-flight turn.** It's a sync method by design (called from a sync route handler). Don't make it await-able.
- **All engine SSE emissions go through `engine._emit(Event(...))`**, not direct `event_queue.put`. `_emit` assigns the monotonic id and appends to the 500-event replay buffer that powers `Last-Event-ID` reconnect. External callers (e.g. `_safe_judge` in routes) may put terminal error events directly — those are fine to skip replay.
- **Single-user, in-memory, no persistence, no auth.** Don't add user-scoping, DB layers, or auth unless the product actually changes.
- **LLM layer is PydanticAI Agents** (`app/agents.py`), not raw OpenAI SDK. The one exception is `app/routes/topic.py`, which intentionally uses `AsyncOpenAI` for a one-shot topic-refine call.
- **Frontend is vanilla JS ES modules** — no bundler, no JSX, no framework. `static/index.html` loads everything via `<script type="module">`. Don't introduce a build step lightly.
- **Stance values are Chinese literals** (`正方` / `反方` / `中立`), enforced by Pydantic `Literal[...]`. UI text and presets are in Chinese; match this when adding strings.
- **Presets live in `app/presets.yaml`**, loaded once via `lru_cache`. Editing the YAML changes preset debaters without code changes — no migration needed.

## Environment quirks

- **No direct PyPI / npm access in this environment.** Use mirrors:
  ```bash
  .venv/bin/pip install --index-url https://mirrors.aliyun.com/pypi/simple <pkg>
  npm install --registry https://registry.npmmirror.com <pkg>
  ```
- `.env` is gitignored but expected at repo root (`API_KEY`, `MODEL`, `BRAVE_API_KEY`, `API_BASE_URL`). Defaults baked into `app/config.py:Settings`.
- No CI, no pre-commit hooks, no PR template. Commits push directly to `main`.

## Workflow conventions

- **Don't add inline comments unless asked.** The codebase style is minimal comments (CLAUDE.md spells this out). Docstrings on public functions/classes are welcome; line-by-line narration of what code does is not.
- **Don't commit or push unless explicitly asked.**
- **Bug-fix commit messages** use `fix: <summary>` with a body listing each bug ID. Refactors use `refactor(scope): ...`. Match this style.

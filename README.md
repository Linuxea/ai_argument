# AI Debate Chatroom

A personal web tool: multiple AI debaters with distinct personas argue a topic in real time. SSE streaming, thinking display, optional web search, and a judge that can call it.

> UI labels and preset personas are 简体中文. The code is English.

## Features

- **Multi-party debate** — preset 正方 / 反方 / 分析家, plus custom debaters with your own personality prompts
- **Real-time SSE streaming** — token-by-token, including the model's thinking/reasoning when the provider exposes it
- **Web search mid-debate** via Brave Search; round 1 is research, round 2+ is conservation mode (max 1 search/round)
- **OpenAI-compatible** — DeepSeek / Volcengine Ark / Ollama / vLLM / LM Studio / OpenAI itself; anything speaking the protocol
- **Global search kill-switch** that respects per-debater `enable_search` (turning it ON never grants search to a debater whose preset disables it)
- **Per-debater bubble tint** so you can tell speakers apart at a glance, plus default-expanded thinking sections and tool cards
- **Editable prompt templates** in `prompts/*.md` — change the wording without touching Python, no ruff/coverage/test cycle
- **Single-user, in-memory** by design — no auth, no database

## Quick start

Requires Python 3.10+. Node 22+ only if you want to run the frontend tests.

```bash
./start.sh                # creates .venv, installs via Aliyun mirror, runs uvicorn on :8000
# or manually:
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000>.

## Configuration

Create `.env` at the repo root (gitignored):

```env
API_BASE_URL=https://api.deepseek.com
API_KEY=sk-...
MODEL=deepseek-reasoner
BRAVE_API_KEY=BSA...   # optional; without it the web_search tool returns a graceful "not configured"
```

| Variable | Default | Notes |
|---|---|---|
| `API_BASE_URL` | `https://api.deepseek.com` | Any OpenAI-compatible endpoint (no trailing `/v1` if the SDK adds it) |
| `API_KEY` | _(empty)_ | Required |
| `MODEL` | `deepseek-reasoner` | Model id sent to the upstream |
| `BRAVE_API_KEY` | _(empty)_ | Enables the `web_search` tool |

`.env` is loaded once at startup via Pydantic Settings; restart the server to pick up changes.

### Provider examples

| Provider | `API_BASE_URL` | `MODEL` example |
|---|---|---|
| DeepSeek (direct) | `https://api.deepseek.com` | `deepseek-reasoner` |
| Volcengine Ark | `https://ark.cn-beijing.volces.com/api/v3` | endpoint id, or model name like `deepseek-v4-pro` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Zhipu GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus` |
| Ollama (local) | `http://localhost:11434/v1` | `qwen2.5:14b` |
| LM Studio (local) | `http://localhost:1234/v1` | _(loaded model name)_ |

All four LLM call sites — debater / judge / extractor / topic-refine — share the same config.

## Using it

1. Enter a topic in the sidebar (Ctrl+Enter starts immediately). The **「优化」** button asks the LLM to sharpen the topic phrasing.
2. Pick 2+ debaters from the list. **Drag to reorder** — that's the turn order. Adjust **最大轮次** if needed.
3. Optionally toggle **启用联网搜索** off to forbid all web search for this debate.
4. Click **开始辩论**. Each debater streams in turn; thinking sections show the reasoning, then the response.
5. Inject your own messages mid-debate via the input bar at the bottom.
6. **暂停** / **继续** to pause and resume; **请裁判点评** asks for a judgment (the debate must be stopped first; auto-fires 5 s after a natural end).
7. `Ctrl+K` opens search. **下载** exports the chat as a self-contained HTML file.

## Customisation

### Add a custom debater (UI)

Fill the sidebar form: name, color, emoji avatar, stance (`正方` / `反方` / `中立`), and a **personality** description.

The personality is treated as the **highest-priority voice/tone instruction** — it overrides the generic "be professional / back up claims" style rules. Write it like you'd direct an actor:

```text
你是"实用主义者"——一位注重实际解决方案的思考者。
你关注成本、收益和现实世界中的可行性。
你避免理想主义的论证，专注于真正有效的方案。
```

A "喜欢胡说八道" debater will actually talk nonsense; the framing is strong on purpose. Structural rules (length, `[[Name]]` mentions, no headers) still apply.

Custom debaters live in process memory and disappear on restart.

### Add or edit a preset debater

Edit `app/presets.yaml`:

```yaml
debaters:
  - name: "实用主义者"
    color: "#9b59b6"
    avatar: "🟣"
    stance: "中立"
    enable_search: true        # default true; set false to forbid web_search for this persona
    personality: |
      你是"实用主义者"——一位注重实际解决方案的思考者。
      你关注成本、收益和现实世界中的可行性。
```

Loaded once at startup via `@lru_cache`. Restart to pick up changes — no migration needed.

### Edit the prompt templates

The seven prompt templates live in `prompts/*.md` and are loaded at import:

| File | Used for |
|---|---|
| `debate_rules.md` | Shared rules every debater sees |
| `search_instructions.md` | The two-phase web-search strategy |
| `strategy_instructions.md` | Round-2+ adaptive counter-strategy |
| `memory_instructions.md` | Cross-round citation patterns |
| `judge.md` | Judge persona |
| `extract_points.md` | Key-claim extractor (JSON out) |
| `topic_refine.md` | Topic-optimisation persona |

Change the wording in the markdown file, restart, done. No Python touched, no tests re-run.

The single piece still inline in `app/agents.py` is the **personality framing wrapper** around `debater.personality` (it's logic, not content — wraps the user's persona text with the override clause).

## Architecture

```
ai_argument/
├── main.py                      # thin: app = create_app()
├── app/
│   ├── __init__.py              # create_app(): lifespan, static mount, routers
│   ├── config.py                # Pydantic Settings (.env) + cached load_presets()
│   ├── deps.py                  # FastAPI Depends + DebaterRepository
│   ├── models.py                # API models + Stance literals + length caps
│   ├── agents.py                # PydanticAI agent factories + _load_prompt(prompts/*.md)
│   ├── tools.py                 # web_search tool (Brave, 1 req/sec, graceful errors)
│   ├── presets.yaml             # preset debaters (3 Chinese personas)
│   ├── engine/
│   │   ├── state.py             # Message / DebateState / Event dataclasses
│   │   ├── prompt.py            # pure build_user_prompt(state, debater)
│   │   ├── event_bus.py         # SSE event queue + 500-event replay buffer
│   │   └── debate.py            # DebateEngine: turn loop, SSE, AgentBundle injection
│   └── routes/                  # debate / debaters / topic
├── prompts/                     # *.md prompt templates — edit here, not Python
├── static/
│   ├── index.html, app.js       # SPA shell + orchestrator
│   ├── modules/
│   │   ├── renderer.js          # streaming state machine (rAF-batched markdown)
│   │   ├── bubble.js            # pure DOM factories (debater / thinking / tool-card / system / user)
│   │   ├── store.js             # MessageStore — canonical record of finalised messages
│   │   ├── markdown.js          # marked config + [[Name]] mention rendering
│   │   ├── search.js            # <dialog> search, reads MessageStore
│   │   ├── sse.js, autoscroll.js, debaters.js, theme.js, toast.js, utils.js
│   ├── styles/                  # cascade-layer CSS (tokens / base / layout / components / messages / search)
│   └── vendor/                  # marked@12.0.2 + lucide@0.469.0 — pinned, local copies
├── tests/                       # backend pytest, 100% coverage enforced (--cov-fail-under=100)
├── tests-js/                    # frontend unit (node --test + jsdom)
└── tests-e2e/                   # Playwright integration smoke
```

**Backend** is FastAPI + PydanticAI Agents end-to-end. Single-user, in-memory; state lives on `app.state.engine` populated during lifespan. The debate engine streams via Server-Sent Events.

**Frontend** is vanilla ES modules — no bundler, no framework. `marked` and `lucide` are vendored under `static/vendor/` to avoid CDN latency.

### SSE event types

`debater_start`, `thinking_chunk`, `debater_finalize`, `debater_chunk`, `debater_end`, `tool_call`, `round_end`, `debate_end`, `debate_paused`, `judge_chunk`, `judge_result`, plus terminal `debate_error` / `judge_error`.

The stream supports `Last-Event-ID` reconnect (500-event replay buffer). One consumer per debate — a second concurrent `/api/debate/stream` returns 409.

### Web search

`web_search` is a PydanticAI tool registered on the search-enabled debater agent. The prompt enforces:

- **Round 1**: search actively, summarise findings, declare readiness — no opening argument yet.
- **Round 2+**: tool is allowed at most once per round and only for surprising, verifiable claims.

A 1 req/sec rate limiter throttles Brave. Any failure (5xx, 429, HTML interstitial, malformed JSON) returns a graceful string the LLM keeps reading from — the debate never crashes on a search outage.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Serve `static/index.html` |
| GET | `/api/presets` | Preset debaters |
| GET | `/api/debaters` | Presets + custom debaters |
| POST | `/api/debaters` | Create a custom debater (name must be unique) |
| POST | `/api/debate/start` | Start a debate (2+ debaters; `search_enabled` toggle) |
| GET | `/api/debate/stream` | SSE event stream (single-consumer; supports `Last-Event-ID`) |
| POST | `/api/debate/message` | Inject a user message into the live debate |
| POST | `/api/debate/stop` | Pause the running debate |
| POST | `/api/debate/resume` | Resume a paused debate |
| POST | `/api/debate/judge` | Request a judgment (debate must be stopped) |
| POST | `/api/topic/refine` | LLM-optimise a topic phrasing |

## Tests

Three independent suites, no shared runner:

```bash
# 1. backend (100% coverage gate)
.venv/bin/python -m pytest tests/

# 2. frontend unit (jsdom + node:test, no build)
npm test

# 3. frontend e2e (Playwright)
npx playwright install chromium     # once
npm run test:e2e
```

For details on the non-obvious testing patterns (AgentBundle injection, jsdom env stubs, the inline-marked-stub convention, real-marked e2e), see `AGENTS.md`.

## Known limits

- **Single user, no persistence** — restart the server and the debate is gone. By design.
- **No upstream LLM timeout** — if the model hangs, the debate stalls behind SSE keepalives. A per-turn `asyncio.timeout` is on the to-do list.
- **`_downloadChat` still reads DOM** rather than the new `MessageStore`. Migration deferred until there's test coverage for the export.
- **No mobile/touch** support for the drag-to-reorder debater list (desktop HTML5 DnD only).

## License

MIT

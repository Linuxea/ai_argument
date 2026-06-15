# AI Debate Chatroom

A personal web-based tool where AI debaters with different personas discuss a user-chosen topic in real-time. Watch the debate unfold, participate by injecting messages, and request a judge's analysis.

> **Note:** The UI and preset debater personas are in Chinese (简体中文).

## Features

- **Multiple AI Debaters**: 3 preset personas (正方/反方/分析家) + custom debaters
- **Real-time Streaming**: SSE-based token-by-token message streaming with thinking/reasoning display
- **Web Search**: AI debaters can search the web (via Brave Search) for evidence during debates
- **User Participation**: Join the debate at any time
- **Topic Refinement**: AI-powered topic optimization for better debate quality
- **Judge Mode**: Get an impartial analysis of the debate
- **OpenAI-Compatible**: Works with any OpenAI-compatible API (DeepSeek, Ollama, vLLM, LM Studio, etc.)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or use the startup script (installs deps and starts server):

```bash
./start.sh [port]
```

### 2. Configure API Key

Create a `.env` file in the project root:

```env
API_KEY="your-api-key-here"
```

Full `.env` options:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API endpoint |
| `API_KEY` | _(empty)_ | API key for the LLM provider |
| `MODEL` | `deepseek-reasoner` | Model name to use |
| `BRAVE_API_KEY` | _(empty)_ | Brave Search API key (optional, enables web search) |

### 3. Run the Application

```bash
python -m uvicorn main:app --reload --port 8000
```

### 4. Open in Browser

Navigate to `http://localhost:8000`

## Usage

1. **Enter a Topic**: Type your debate topic in the sidebar (e.g., "AI 是否应该取代教师？")
2. **Select Debaters**: Check at least 2 debaters from the list
3. **Start Debate**: Click "开始辩论" and watch the AI debaters discuss
4. **Participate**: Type messages and click "发送" to inject your thoughts
5. **Judge**: Click "评判" for an impartial analysis

## Configuration

### Using with Other Providers

| Provider | Base URL | Notes |
|----------|----------|-------|
| DeepSeek | `https://api.deepseek.com` | Default, requires API key |
| Ollama | `http://localhost:11434/v1` | Local, no API key needed |
| LM Studio | `http://localhost:1234/v1` | Start server in LM Studio |
| vLLM | `http://localhost:8000/v1` | Run `vllm serve <model>` |
| OpenAI | `https://api.openai.com/v1` | Requires API key |

### Using with Ollama (Local Models)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Then set in .env:
# API_BASE_URL=http://localhost:11434/v1
# API_KEY=ollama
# MODEL=llama3
```

### Web Search (Optional)

To enable web search for debaters, get a Brave Search API key from [brave.com/search/api](https://brave.com/search/api/) and add it to your `.env`:

```env
BRAVE_API_KEY="your-brave-api-key"
```

## Custom Debaters

Create custom debaters in the UI:

1. Enter a **Name** (e.g., "实用主义者")
2. Choose a **Color** (for message styling)
3. Pick an **Emoji** avatar
4. Select a **Stance**: 正方 (For), 反对 (Against), or 中立 (Neutral)
5. Toggle **Web Search** on/off for this debater
6. Write a **Personality** description

Example personality:
```
你是"实用主义者"——一位注重实际解决方案的思考者。
你关注成本、收益和现实世界中的可行性。
你避免理想主义的论证，专注于真正有效的方案。
```

## Project Structure

```
ai_argument/
├── main.py              # Entry point: app = create_app()
├── app/                 # Application package
│   ├── __init__.py      # create_app() factory (lifespan, static, routers)
│   ├── config.py        # Pydantic Settings (from .env) + cached presets
│   ├── deps.py          # FastAPI Depends providers + DebaterRepository
│   ├── models.py        # Pydantic models + validation (length caps)
│   ├── agents.py        # PydanticAI agent definitions + prompt templates
│   ├── tools.py         # web_search tool (Brave Search, rate-limited)
│   ├── presets.yaml     # Pre-defined debater personas (Chinese)
│   ├── engine/
│   │   ├── state.py     # Message / DebateState / Event dataclasses
│   │   └── debate.py    # DebateEngine (turns, prompt building, SSE events)
│   └── routes/
│       ├── debate.py    # /api/debate/* (start, stream, message, judge...)
│       ├── debaters.py  # /api/presets, /api/debaters
│       └── topic.py     # /api/topic/refine
├── start.sh             # Startup script (install + run)
├── static/
│   ├── index.html       # Chat UI (Chinese)
│   ├── style.css        # Dark theme styling
│   └── app.js           # SSE handling, DOM updates
├── tests/               # Unit and integration tests
└── .env                 # API configuration (not in repo)
```

The backend uses **dependency injection** — routes receive the `DebateEngine`
and `DebaterRepository` via FastAPI `Depends`, reading from `app.state`
populated at startup. Configuration is validated by **Pydantic Settings**.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser (Single HTML page)                  │
│  ┌─────────┐  ┌──────────────────────────┐  │
│  │ Sidebar  │  │   Chat Area               │  │
│  │ - Topic  │  │   Messages stream in      │  │
│  │ - Debaters│  │   real-time via SSE       │  │
│  │ - Settings│  │   + thinking display      │  │
│  └─────────┘  └──────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ SSE stream + REST API
┌──────────────────▼──────────────────────────┐
│  FastAPI Backend                             │
│  ┌────────────┐  ┌────────────────────────┐ │
│  │ REST API   │  │ Debate Engine          │ │
│  │ /api/*     │  │ - Turn management      │ │
│  │            │  │ - PydanticAI agents    │ │
│  └────────────┘  └────────────────────────┘ │
│                  ┌────────────────────────┐ │
│                  │ PydanticAI Agents       │ │
│                  │ - Debater (w/ search)   │ │
│                  │ - Debater (no search)   │ │
│                  │ - Judge                 │ │
│                  └────────────┬───────────┘ │
│                  ┌────────────▼───────────┐ │
│                  │ Brave Search API        │ │
│                  │ (optional web search)   │ │
│                  └────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### How AI-to-AI Communication Works

The debate engine uses **PydanticAI Agents** for LLM calls. Each debater has its own agent instance with per-turn message history:

1. The engine builds a user prompt from the debate history:
   - Other debaters' messages are included as `[Name]: content`
   - The debater's own messages are excluded (they're already in `message_history` as prior `ModelResponse` entries)
2. The agent's system prompt includes date context, shared debate rules, stance instructions, personality, and optional search instructions
3. First-turn debaters receive an opening-statement prompt instead of history
4. A round countdown is included when `max_rounds` is set
5. Messages stream back via SSE, including thinking/reasoning tokens and tool call events

### Web Search in Debates

When `enable_search` is enabled for a debater and `BRAVE_API_KEY` is configured:

- **Round 1**: The debater gathers knowledge — searches the web for facts, statistics, and recent developments
- **Round 2+**: Conservation mode — relies on gathered knowledge, with rare exception-based searches (max 1/round)
- Search results are displayed as tool-call cards in the UI
- A rate limiter (1 req/sec) prevents API abuse

### SSE Events

Event types emitted to `/api/debate/stream`:

| Event | Description |
|-------|-------------|
| `debater_start` | A debater begins their turn |
| `thinking_chunk` | Reasoning/thinking token stream (for models with thinking) |
| `debater_finalize` | Transition from thinking to response |
| `debater_chunk` | Response text token stream |
| `debater_end` | A debater finishes their turn |
| `tool_call` | Web search executed (with query and result summary) |
| `round_end` | A debate round completes |
| `debate_end` | Debate ends (max rounds reached) |
| `debate_paused` | Debate paused by user |
| `judge_chunk` | Judge analysis token stream |
| `judge_result` | Judge analysis complete |

### Debate Rules (enforced in prompts)

- 80–200 words per response
- Respond to actual points, not just restate position
- Reference other debaters with `[[Name]]` syntax
- Back up claims with reasoning or examples
- Rebuttals must advance own argument, not just deny opponents
- No headers, labels, or numbered sections — speak naturally

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

## Preset Debaters

Defined in `presets.yaml` with Chinese names and personality descriptions:

| Name | Avatar | Stance | Search | Style |
|------|--------|--------|--------|-------|
| 正方 | 🟢 | 正方 | Yes | Passionate advocate, cites success stories and precedents |
| 反方 | 🔴 | 反方 | Yes | Sharp critic, finds logical flaws and weak evidence |
| 分析家 | 🔵 | 中立 | No | Data-driven, weighs multiple perspectives, spots false dichotomies |

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

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_debate_engine.py -v
```

## Limitations

- **Single User**: Designed as a personal tool (not multi-user)
- **No Persistence**: Debate state is in-memory only
- **Session-Only Custom Debaters**: Custom debaters don't persist across restarts

## License

MIT

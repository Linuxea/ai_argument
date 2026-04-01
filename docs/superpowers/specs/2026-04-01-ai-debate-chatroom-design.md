# AI Debate Chatroom - Design Spec

## Summary

A personal web-based tool where AI debaters with different personas discuss a user-chosen topic in real-time. The user watches the debate unfold, can participate by injecting messages, and can request a judge's analysis at any time. Built with Python (FastAPI) backend and vanilla HTML/CSS/JS frontend.

## Architecture

```
Browser (Single HTML page)
  ├── Sidebar: topic input, debater selection, custom debater creation, settings
  └── Chat area: timeline-style message stream with debater bubbles + user input

FastAPI Backend
  ├── REST endpoints: start/stop debate, inject message, judge
  ├── SSE endpoint: stream debater responses token-by-token
  ├── Debate Engine: turn management, prompt construction, history tracking
  └── LLM Client: OpenAI-compatible API wrapper (supports OpenAI, Ollama, vLLM, etc.)
```

No database. All state is in-memory per session.

## AI-to-AI Communication

Debaters communicate by sharing a growing conversation history. The debate engine calls the LLM API once per turn, building the message array with full context:

- Each debater sees the **entire conversation history** from all previous turns
- The engine constructs messages with correct role mapping per debater's perspective
- Full history is kept (no summarization) — user has abundant tokens

### Message Role Mapping

For Debater A's API call:

| Content | Role |
|---------|------|
| Debater A's persona instructions | `system` |
| Topic description | `user` |
| Debater A's own past responses | `assistant` |
| Other debaters' responses | `user` (prefixed with `[Name]:`) |
| User messages | `user` (prefixed with `[You]:`) |

Consecutive same-role messages are allowed by the OpenAI API. The last message is always `user` or `system` (never `assistant`) so the model has something to respond to.

## Debater Personas

### Preset Debaters (YAML config)

Defined in `presets.yaml` with these fields:

```yaml
debaters:
  - name: "The Skeptic"
    color: "#e74c3c"
    avatar: "🔴"
    stance: "against"
    personality: |
      You are a critical thinker who questions assumptions.
      You look for flaws in arguments and play devil's advocate.
      You are direct but respectful.
```

Predefined personas:
- **The Skeptic** (red) — questions assumptions, plays devil's advocate
- **The Optimist** (green) — sees potential, builds on ideas
- **The Analyst** (blue) — data-driven, examines both sides

### Custom Debaters

Users create custom debaters through the sidebar form:
- Name (text)
- Color (color picker)
- Avatar (emoji selector)
- Stance: for / against / neutral
- Personality description (textarea)

Custom debaters are stored in-memory for the session.

## Frontend UI

### Layout

- **Sidebar** (left, ~300px): topic input, debater checkboxes, custom debater form, API settings, start/stop buttons
- **Chat area** (right, flexible width): timeline of messages, user input bar at bottom

### Message Display

Messages appear in chronological order as a timeline, like a group chat:
- Each debater has a distinct color (from their config) and avatar emoji
- Messages stream in token-by-token as the debater "speaks"
- A "typing..." indicator shows which debater is currently responding
- User messages appear in a neutral style with a distinct avatar

### SSE Event Types

| Event | Payload | When |
|-------|---------|------|
| `debater_start` | `{debater_name, color}` | A debater begins their turn |
| `debater_chunk` | `{debater_name, text_chunk}` | Streaming token-by-token |
| `debater_end` | `{debater_name, full_text}` | Debater finished their turn |
| `round_end` | `{round_number}` | All debaters spoke in this round |
| `user_prompt` | `{message}` | User's message is injected |
| `debate_end` | `{reason}` | Debate stopped |
| `judge_result` | `{judgment_text}` | Judge's analysis |

## User Interactions

### Start Debate
1. Enter topic in sidebar
2. Select 2-5 debaters (checkboxes)
3. Click "Start Debate"
4. Debaters begin discussing — messages stream via SSE

### During Debate
- Type message + Send → message injected into conversation as `[You]:` → next debater sees it
- Click "Stop" → debate pauses
- Click "Resume" → debate continues

### Judge Mode
- Click "Be Judge" → LLM called with a judge system prompt (separate from debater personas)
- Judge reads entire conversation and gives structured analysis:
  - Summary of each debater's key arguments
  - Strengths and weaknesses
  - Overall assessment

## Backend Components

### `main.py` — FastAPI Application
- Serves static files (HTML/CSS/JS)
- Defines all API routes
- Manages SSE connection lifecycle
- Dependency injection for debate engine and LLM client

### `debate_engine.py` — Core Logic
- Manages debate state: topic, selected debaters, conversation history, current turn
- Constructs per-debater message arrays with correct role mapping
- Controls turn order (round-robin through selected debaters)
- Handles user message injection
- Generates judge prompt and processes result

### `llm_client.py` — API Wrapper
- Thin wrapper around `openai` Python SDK
- Configurable base URL and API key (supports any OpenAI-compatible endpoint)
- Configurable model name
- Streaming support (`stream=True`)
- Error handling for rate limits, context overflow, connection issues

### `models.py` — Data Models (Pydantic)
- `Debater`: name, color, avatar, stance, personality
- `DebateConfig`: topic, selected debater names, model settings
- `Message`: role, content, debater_name, timestamp
- `DebateState`: active/inactive, current_round, current_turn_index, history

### `config.py` — Configuration
- API base URL, API key, default model
- Default number of rounds
- Preset debater loading from YAML

### `presets.yaml` — Persona Definitions
- List of pre-defined debater configurations

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Serve the HTML page |
| `GET` | `/api/presets` | List preset debaters |
| `POST` | `/api/debate/start` | Start debate (body: topic, debater names) |
| `GET` | `/api/debate/stream` | SSE endpoint for live messages |
| `POST` | `/api/debate/message` | Inject user message (body: message text) |
| `POST` | `/api/debate/stop` | Stop/pause the debate |
| `POST` | `/api/debate/resume` | Resume a paused debate |
| `POST` | `/api/debate/judge` | Request judge's analysis |
| `POST` | `/api/debaters` | Create custom debater (body: name, color, avatar, stance, personality) |

## Project Structure

```
ai_argument/
├── main.py              # FastAPI app, routes, SSE endpoint
├── debate_engine.py     # Core logic: turns, prompts, history
├── llm_client.py        # OpenAI-compatible API wrapper
├── models.py            # Pydantic models
├── config.py            # Settings, preset loading
├── presets.yaml         # Pre-defined debater personas
├── static/
│   ├── index.html       # Single-page chat UI
│   ├── style.css        # Chat bubbles, layout, sidebar
│   └── app.js           # SSE handling, DOM updates, UI logic
├── requirements.txt     # fastapi, uvicorn, openai, pyyaml
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-01-ai-debate-chatroom-design.md
```

## Dependencies

- `fastapi` — web framework
- `uvicorn` — ASGI server
- `openai` — OpenAI-compatible API client
- `pydantic` — data validation
- `pyyaml` — YAML config parsing

## Error Handling

- LLM API errors: display error message in chat, allow retry
- SSE connection drops: auto-reconnect with EventSource
- Invalid debater selection: validate before starting (min 2 debaters)
- Context window overflow: warn user when approaching limit, suggest stopping

## Out of Scope (YAGNI)

- Multi-user support / authentication
- Persistent storage / database
- Debate export / sharing
- Audio/voice debaters
- Multiple concurrent debates

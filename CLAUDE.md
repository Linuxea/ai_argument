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

## Architecture

### Core Algorithm: Message Role Mapping

The key algorithm is in `debate_engine.py:build_messages()`. When building the message array for a debater's API call:

- Debater's **own** past messages → `role: "assistant"`
- **Other** debaters' messages → `role: "user"` with `[Name]:` prefix
- User messages → `role: "user"` with `[You]:` prefix

This allows each LLM call to see the full conversation history while maintaining its persona.

### Data Flow

```
User starts debate → main.py:start_debate()
  → debate_engine.start(topic, debaters)
  → asyncio.create_task(debate_engine.run_loop())
  → run_loop() calls run_turn() for each debater in round-robin
  → run_turn() builds messages, streams LLM response, emits SSE events
  → Frontend receives SSE events, updates DOM in real-time
```

### SSE Events

Events are defined in `debate_engine.py` as the `Event` dataclass and emitted to `event_queue`. The SSE endpoint at `/api/debate/stream` yields these as `event: <type>\ndata: <json>\n\n`.

Event types: `debater_start`, `debater_chunk`, `debater_end`, `round_end`, `debate_end`, `judge_chunk`, `judge_result`

### Global State

The app uses module-level globals (`debate_engine`, `custom_debaters`) in `main.py`. This is intentional for a single-user personal tool but means no multi-user support.

## Key Files

| File | Purpose |
|------|---------|
| `debate_engine.py` | Core logic: state, message building, turn order, SSE events |
| `main.py` | FastAPI routes, SSE endpoint, lifespan management |
| `llm_client.py` | Thin wrapper around OpenAI SDK with streaming |
| `presets.yaml` | Debater persona definitions |
| `config.py` | Settings class, loads presets from YAML |
| `models.py` | Pydantic models for API contracts |

## Configuration

Defaults to Ollama at `http://localhost:11434/v1`. Change via:
- UI sidebar (requires server restart)
- Environment variables or `config.py` defaults
- Settings are stored in `config.py:Settings` class

## Adding a New Preset Debater

Edit `presets.yaml`:

```yaml
debaters:
  - name: "The Pragmatist"
    color: "#9b59b6"
    avatar: "🟣"
    stance: "neutral"
    personality: |
      You are a pragmatic thinker who focuses on practical solutions.
      You care about costs, benefits, and real-world implementation.
```

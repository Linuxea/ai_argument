# AI Debate Chatroom

A personal web-based tool where AI debaters with different personas discuss a user-chosen topic in real-time. Watch the debate unfold, participate by injecting messages, and request a judge's analysis.

## Features

- **Multiple AI Debaters**: 3 preset personas (Skeptic, Optimist, Analyst) + custom debaters
- **Real-time Streaming**: SSE-based token-by-token message streaming
- **User Participation**: Join the debate at any time
- **Judge Mode**: Get an impartial analysis of the debate
- **OpenAI-Compatible**: Works with any OpenAI-compatible API (Ollama, vLLM, LM Studio, etc.)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Your LLM Server

The app defaults to Ollama running locally:

```bash
# Install Ollama (if not already)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Ollama serves at http://localhost:11434 by default
```

### 3. Run the Application

```bash
python -m uvicorn main:app --reload --port 8000
```

### 4. Open in Browser

Navigate to `http://localhost:8000`

## Usage

1. **Enter a Topic**: Type your debate topic in the sidebar (e.g., "Should AI replace teachers?")
2. **Select Debaters**: Check at least 2 debaters from the list
3. **Start Debate**: Click "Start Debate" and watch the AI debaters discuss
4. **Participate**: Type messages and click "Send" to inject your thoughts
5. **Judge**: Click "Be Judge" for an impartial analysis

## Configuration

### API Settings

Configure in the UI sidebar or modify `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| API Base URL | `http://localhost:11434/v1` | OpenAI-compatible API endpoint |
| API Key | `ollama` | API key (often not needed for local models) |
| Model | `llama3` | Model name to use |

### Using with OpenAI

```python
# config.py
class Settings:
    def __init__(
        self,
        api_base_url: str = "https://api.openai.com/v1",
        api_key: str = "sk-your-key",
        model: str = "gpt-4",
    ):
```

### Using with Other Providers

| Provider | Base URL | Notes |
|----------|----------|-------|
| Ollama | `http://localhost:11434/v1` | Default |
| LM Studio | `http://localhost:1234/v1` | Start server in LM Studio |
| vLLM | `http://localhost:8000/v1` | Run `vllm serve <model>` |
| OpenAI | `https://api.openai.com/v1` | Requires API key |

## Custom Debaters

Create custom debaters in the UI:

1. Enter a **Name** (e.g., "The Pragmatist")
2. Choose a **Color** (for message styling)
3. Pick an **Emoji** avatar
4. Select a **Stance**: For, Against, or Neutral
5. Write a **Personality** description

Example personality:
```
You are a pragmatic thinker who focuses on practical solutions.
You care about costs, benefits, and real-world implementation.
You avoid idealistic arguments and focus on what actually works.
```

## Project Structure

```
ai_argument/
├── main.py              # FastAPI application (routes, SSE)
├── debate_engine.py     # Core logic (message building, turns)
├── llm_client.py        # OpenAI-compatible client
├── models.py            # Pydantic data models
├── config.py            # Settings and preset loading
├── presets.yaml         # Pre-defined debater personas
├── static/
│   ├── index.html       # Chat UI
│   ├── style.css        # Dark theme styling
│   └── app.js           # SSE handling, DOM updates
├── tests/               # Unit and integration tests
└── README.md
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser (Single HTML page)                  │
│  ┌─────────┐  ┌──────────────────────────┐  │
│  │ Sidebar  │  │   Chat Area               │  │
│  │ - Topic  │  │   Messages stream in      │  │
│  │ - Debaters│  │   real-time via SSE       │  │
│  │ - Settings│  │                           │  │
│  └─────────┘  └──────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ SSE stream + REST API
┌──────────────────▼──────────────────────────┐
│  FastAPI Backend                             │
│  ┌────────────┐  ┌────────────────────────┐ │
│  │ REST API   │  │ Debate Engine          │ │
│  │ /api/*     │  │ - Turn management      │ │
│  │            │  │ - Message building     │ │
│  └────────────┘  └────────────────────────┘ │
│                  ┌────────────────────────┐ │
│                  │ LLM Client              │ │
│                  │ (OpenAI-compatible)     │ │
│                  └────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### How AI-to-AI Communication Works

Debaters share a growing conversation history. Each turn:

1. The engine builds a message array with correct role mapping:
   - Debater's own past messages → `assistant` role
   - Other debaters' messages → `user` role with `[Name]:` prefix

2. This lets the model see the full conversation while maintaining its persona

3. Messages stream back via SSE for real-time display

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

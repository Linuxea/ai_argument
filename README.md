# AI Debate Chatroom

A personal web-based tool where AI debaters with different personas discuss a user-chosen topic in real-time. Watch the debate unfold, participate by injecting messages, and request a judge's analysis.

> **Note:** The UI and preset debater personas are in Chinese (简体中文).

## Features

- **Multiple AI Debaters**: 3 preset personas (质疑者/乐观派/分析家) + custom debaters
- **Real-time Streaming**: SSE-based token-by-token message streaming
- **User Participation**: Join the debate at any time
- **Judge Mode**: Get an impartial analysis of the debate
- **OpenAI-Compatible**: Works with any OpenAI-compatible API (DeepSeek, Ollama, vLLM, LM Studio, etc.)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Set your DeepSeek API key (the default provider):

```bash
export DEEPSEEK_API_KEY="your-api-key-here"
```

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

### API Settings

Configure in the UI sidebar or set environment variables:

| Setting | Default | Description |
|---------|---------|-------------|
| API Base URL | `https://api.deepseek.com` | OpenAI-compatible API endpoint |
| API Key | from `DEEPSEEK_API_KEY` | API key |
| Model | `deepseek-chat` | Model name to use |

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

# Then configure in the UI sidebar:
# API Base URL: http://localhost:11434/v1
# API Key: ollama
# Model: llama3
```

## Custom Debaters

Create custom debaters in the UI:

1. Enter a **Name** (e.g., "实用主义者")
2. Choose a **Color** (for message styling)
3. Pick an **Emoji** avatar
4. Select a **Stance**: 支持 (For), 反对 (Against), or 中立 (Neutral)
5. Write a **Personality** description

Example personality:
```
你是"实用主义者"——一位注重实际解决方案的思考者。
你关注成本、收益和现实世界中的可行性。
你避免理想主义的论证，专注于真正有效的方案。
```

## Project Structure

```
ai_argument/
├── main.py              # FastAPI application (routes, SSE)
├── debate_engine.py     # Core logic (message building, turns)
├── llm_client.py        # OpenAI-compatible client
├── models.py            # Pydantic data models
├── config.py            # Settings and preset loading
├── presets.yaml         # Pre-defined debater personas (Chinese)
├── static/
│   ├── index.html       # Chat UI (Chinese)
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
2. The system prompt includes shared debate rules, stance instructions, and the debater's unique personality
3. First-turn debaters receive an opening-statement prompt instead of history
4. A round countdown is included when `max_rounds` is set
5. Messages stream back via SSE for real-time display

### Debate Rules (enforced in prompts)

- 80–200 words per response
- Respond to actual points, not just restate position
- Reference other debaters with `[[Name]]` syntax
- Back up claims with reasoning or examples
- Rebuttals must advance own argument, not just deny opponents
- No headers, labels, or numbered sections — speak naturally

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

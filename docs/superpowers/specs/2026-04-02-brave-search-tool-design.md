# Brave Search Tool for Debate Agents

**Date:** 2026-04-02
**Status:** Approved

## Goal

Add a Brave Search web search tool to debater agents, allowing LLMs to automatically look up factual information during debates. The frontend displays tool calls as visually distinct "search cards" between normal chat bubbles, so users can see when and what a debater searched for.

## Requirements

- Debater agents automatically decide when to search (LLM-driven, not user-triggered)
- Only debaters get the search tool; the judge agent does not
- Multiple searches allowed within a single turn
- Tool calls appear as separate UI bubbles (search cards) interleaved with text bubbles
- Graceful degradation: debate works normally without a Brave API key

## Architecture

### New File: `tools.py`

Contains the `web_search` tool function registered on the debater agent via PydanticAI's tool mechanism.

```python
# tools.py
import httpx
from pydantic_ai import RunContext
from agents import DebaterDeps

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 5
MAX_TOTAL_CHARS = 1000

async def web_search(ctx: RunContext[DebaterDeps], query: str) -> str:
    """Search the web for factual information to support your argument.

    Use this when you need data, statistics, recent events, or verifiable
    facts. Do NOT use for opinions or general reasoning.

    Args:
        query: A concise search query (1-10 words recommended).
    """
    api_key = ctx.deps.brave_api_key  # or read from settings/global
    if not api_key:
        return "Search is not configured (no API key). Proceed without search results."

    async with httpx.AsyncClient() as client:
        response = await client.get(
            BRAVE_ENDPOINT,
            headers={"X-Subscription-Token": api_key},
            params={"q": query, "count": MAX_RESULTS},
        )
        response.raise_for_status()
        data = response.json()

    results = []
    total_chars = 0
    for item in data.get("web", {}).get("results", []):
        snippet = f"- {item['title']}: {item.get('description', '')}"
        if total_chars + len(snippet) > MAX_TOTAL_CHARS:
            break
        results.append(snippet)
        total_chars += len(snippet)

    if not results:
        return f"No results found for '{query}'."

    return f"Search results for '{query}':\n" + "\n".join(results)
```

### Changes to `agents.py`

Register the search tool on the debater agent:

```python
from tools import web_search

def create_debater_agent(model: str) -> Agent[DebaterDeps, str]:
    agent: Agent[DebaterDeps, str] = Agent(
        model,
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[web_search],  # <-- add search tool
    )
    return agent
```

No changes to `create_judge_agent` — judge does not get search capability.

### Changes to `DebaterDeps`

Add `brave_api_key` field so the tool can access it via `ctx.deps`:

```python
@dataclass
class DebaterDeps:
    topic: str
    debater: Debater
    round_number: int
    max_rounds: int | None
    brave_api_key: str | None = None  # <-- new
```

### Changes to `config.py`

Add Brave API key to `Settings`:

```python
class Settings:
    def __init__(self, ...):
        ...
        self.brave_api_key = os.environ.get("BRAVE_API_KEY", "")
```

### Changes to `debate_engine.py`

#### 1. Pass `brave_api_key` through deps

```python
# run_turn() — when constructing deps
deps = DebaterDeps(
    topic=self.state.topic,
    debater=debater,
    round_number=self.state.current_round,
    max_rounds=self.state.max_rounds,
    brave_api_key=self.brave_api_key,  # <-- new
)
```

Store `brave_api_key` on `DebateEngine.__init__()` from settings.

#### 2. Add `event_stream_handler` to detect tool calls

Use PydanticAI's `event_stream_handler` parameter in `run_stream()` to monitor tool execution and emit SSE events:

```python
async def _handle_events(self, ctx, event_stream, debater_name):
    """Monitor agent execution, emit SSE events for tool calls."""
    current_query = None

    async for event in event_stream:
        if isinstance(event, FunctionToolCallEvent):
            current_query = event.part.args.get("query", "")
        elif isinstance(event, FunctionToolResultEvent):
            result_text = event.result.content[:200] if event.result else ""
            await self.event_queue.put(Event(
                type="tool_call",
                payload={
                    "debater_name": debater_name,
                    "tool_name": "web_search",
                    "query": current_query or "",
                    "result_summary": result_text,
                }
            ))
```

Pass to `run_stream()`:

```python
async with self.debater_agent.run_stream(
    user_prompt,
    deps=deps,
    message_history=self._history[debater.name],
    event_stream_handler=lambda ctx, es: self._handle_events(ctx, es, debater.name),
) as result:
    async for delta in result.stream_text(delta=True):
        full_text += delta
        await self.event_queue.put(Event(
            type="debater_chunk",
            payload={"debater_name": debater.name, "text_chunk": delta},
        ))
```

### New SSE Event

| Event | Payload | When |
|---|---|---|
| `tool_call` | `{debater_name, tool_name, query, result_summary}` | Tool finishes execution |

The frontend uses this event to finalize the current text bubble and render a search card.

## Frontend Changes

### `app.js` — SSE handler for `tool_call`

```javascript
this.eventSource.addEventListener('tool_call', (e) => {
    const data = JSON.parse(e.data);
    // Finalize current text bubble (if any)
    this.finalizeMessage();
    // Render search card as a distinct bubble
    this.addToolCard(data.debater_name, data.tool_name, data.query, data.result_summary);
});
```

### `app.js` — `addToolCard()` method

Creates a visually distinct bubble for tool results:

```javascript
addToolCard(debaterName, toolName, query, resultSummary) {
    const message = document.createElement('div');
    message.className = 'message ai tool-card';

    const header = document.createElement('div');
    header.className = 'message-header';
    // Use saved _currentDebater* fields (set during debater_start)
    const avatarEl = document.createElement('span');
    avatarEl.className = 'message-avatar';
    avatarEl.textContent = this._currentDebaterAvatar;
    const senderEl = document.createElement('span');
    senderEl.className = 'message-sender';
    senderEl.style.color = this.sanitizeColor(this._currentDebaterColor);
    senderEl.textContent = debaterName;
    header.appendChild(avatarEl);
    header.appendChild(senderEl);

    const content = document.createElement('div');
    content.className = 'tool-card-content';
    content.innerHTML = `
        <div class="tool-card-label">🔍 Searched: "${this.escapeHtml(query)}"</div>
        <div class="tool-card-results">${this.renderContent(resultSummary)}</div>
    `;

    message.appendChild(header);
    message.appendChild(content);
    this.messages.appendChild(message);
}
```

### `style.css` — Search card styles

```css
.tool-card .tool-card-content {
    background: var(--bg-input);
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    border: 1px dashed var(--border);
    font-size: 0.82rem;
    color: var(--text-soft);
    line-height: 1.5;
}

.tool-card .tool-card-label {
    font-weight: 600;
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-bottom: 6px;
}

.tool-card .tool-card-results {
    font-size: 0.82rem;
}
```

Key visual differences from normal chat bubbles:
- Dashed border instead of solid left border
- Smaller font, muted colors
- No background elevation — flat style
- Collapsible by default (can expand for full results)

### Multi-bubble flow in frontend

The existing `debater_start` / `debater_chunk` / `debater_end` cycle still works. The `tool_call` event sits between chunks:

```
SSE events:                              Frontend bubbles:
─────────────────────────────────────    ─────────────────────
debater_start                            Create bubble 1
debater_chunk × N                        Append text to bubble 1
tool_call                                Finalize bubble 1, render search card
debater_chunk × N                        Create bubble 2, append text
debater_end                              Finalize bubble 2
```

When `debater_chunk` arrives but there's no active bubble (because `tool_call` finalized it), the handler creates a new bubble for the same debater. This is achieved by checking `this.currentMessageEl === null` in `appendToMessage()`:

```javascript
appendToMessage(text) {
    if (!this.currentMessageEl) {
        // No active bubble — create one for the same debater
        // (debater_start data was saved earlier)
        this.createMessage(this._currentDebaterName, this._currentDebaterColor, this._currentDebaterAvatar);
    }
    // ... existing append logic
}
```

Track current debater info so new bubbles after tool calls reuse the same name/avatar/color.

## Error Handling

| Scenario | Behavior |
|---|---|
| No `BRAVE_API_KEY` set | Tool returns "Search not configured" message. LLM sees this and continues debating without search. `tool_call` SSE event still fires (so user sees a card), but with a clear "not configured" label. |
| Brave API network error | Tool catches exception, returns error message. LLM continues without data. |
| Brave API rate limit (429) | Tool catches exception, returns "Search rate limited." LLM adapts. |
| Empty search results | Tool returns "No results found for '...'." LLM adjusts argument. |

All errors are soft failures — the debate never stops because of a search issue.

## Dependencies

- `httpx` — for async HTTP calls to Brave Search API (add to requirements)

## Configuration

| Setting | Value |
|---|---|
| Env var | `BRAVE_API_KEY` |
| API endpoint | `https://api.search.brave.com/res/v1/web/search` |
| Max results per query | 5 |
| Max total chars in result | 1000 |
| Result summary truncation | 200 chars (for SSE event payload) |

## Testing Strategy

1. **Unit tests** (`tests/test_tools.py`): Mock Brave API responses, test `web_search()` with various inputs (normal, empty, error)
2. **Unit tests** (`tests/test_agents.py`): Verify debater agent has tool registered, judge agent does not
3. **Integration tests** (`tests/test_debate_engine.py`): Verify tool_call SSE events are emitted during streaming
4. **Frontend tests**: Multi-bubble rendering, search card styling (manual testing for now)

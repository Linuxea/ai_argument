# Thinking Mode Design Spec

## Overview

Add support for reasoning models (DeepSeek-R1, Claude with thinking, OpenAI o1/o3) in the debate app. When a reasoning model is selected, debaters' thinking process is streamed live and rendered inline within their message bubbles.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| When to enable | Auto-detect by model | No manual toggle needed; PydanticAI handles provider differences |
| Display style | Inline tag within message | Most compact; doesn't break conversation flow |
| Streaming | Live, real-time | Most engaging; users see reasoning as it happens |
| Judge thinking | No (debaters only) | Simpler; judge output should be decisive, not show uncertainty |
| Text styling | Smaller font (11px) | Clear hierarchy through size; least visually disruptive |
| Backend approach | Let PydanticAI handle it | Future-proof; no fragile model-name detection |

## Backend Changes

### agents.py

Add `model_settings={'thinking': True}` to the debater agent constructors:

```python
def create_debater_agent(...) -> Agent[DebaterDeps, str]:
    agent = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[web_search],
        model_settings={'thinking': True},  # <-- add
    )
    return agent

def create_debater_agent_no_search(...) -> Agent[DebaterDeps, str]:
    agent = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[],
        model_settings={'thinking': True},  # <-- add
    )
    return agent
```

The `create_judge_agent` function is **not changed** (no thinking for judge).

PydanticAI silently ignores `thinking: True` on models that don't support it. No model-name detection needed.

### debate_engine.py

#### New SSE event type

Add a `thinking_chunk` event type. Emitted during the thinking phase, before the reply text starts.

Event payload:
```json
{
  "debater_name": "乐观派",
  "text_chunk": "让我分析这个问题的核心论点..."
}
```

No separate `thinking_start` or `thinking_end` events needed:
- **Start**: The frontend creates thinking elements on the first `thinking_chunk`.
- **End**: Detected by the frontend when the first `debater_chunk` arrives after thinking chunks, or by the existing `debater_finalize` event.

#### Changes to run_turn()

Add a `_thinking_active` local flag. Insert two new branches in the event handling chain:

```python
# After existing TextPart handlers, add:

elif isinstance(event, PartStartEvent) and isinstance(event.part, ThinkingPart):
    _thinking_active = True
    initial = event.part.content
    if initial:
        await self.event_queue.put(Event(
            type="thinking_chunk",
            payload={"debater_name": debater.name, "text_chunk": initial},
        ))

elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, ThinkingPartDelta):
    delta = event.delta.content_delta
    await self.event_queue.put(Event(
        type="thinking_chunk",
        payload={"debater_name": debater.name, "text_chunk": delta},
    ))
```

**Transition from thinking to text:** When the first `TextPart`/`TextPartDelta` arrives after thinking, emit `debater_finalize` to signal the frontend to close the thinking section, then proceed with normal text handling.

In the existing `TextPart` handler block, add a check at the top:

```python
if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
    if _thinking_active:
        _thinking_active = False
        await self.event_queue.put(Event(type="debater_finalize", payload={}))
    # ... existing TextPart handling
elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
    if _thinking_active:
        _thinking_active = False
        await self.event_queue.put(Event(type="debater_finalize", payload={}))
    # ... existing TextPartDelta handling
```

#### Import update

Add `ThinkingPart` and `ThinkingPartDelta` to imports from `pydantic_ai.messages`:

```python
from pydantic_ai.messages import (
    ModelMessage, PartStartEvent, PartDeltaEvent,
    TextPart, TextPartDelta,
    ThinkingPart, ThinkingPartDelta,  # <-- add
)
```

## Frontend Changes

### static/app.js

#### New SSE handler

Add in `connectSSE()`, before the existing `debater_chunk` handler:

```javascript
this.eventSource.addEventListener('thinking_chunk', (e) => {
    const data = this._parseSSEData(e, 'thinking_chunk');
    if (!data) return;
    this.appendToThinking(data.text_chunk);
});
```

#### New method: appendToThinking(text)

```javascript
appendToThinking(text) {
    // Ensure message bubble exists
    if (!this.currentMessageEl) {
        this.createMessage(
            this._currentDebaterName || 'Unknown',
            this._currentDebaterColor || '#333333',
            this._currentDebaterAvatar || '💬',
            'debater'
        );
    }

    // Create thinking elements on first call
    if (!this.currentMessageEl.querySelector('.thinking-text')) {
        const tag = document.createElement('span');
        tag.className = 'thinking-tag';
        tag.textContent = '💭 thinking';

        const thinkingSpan = document.createElement('span');
        thinkingSpan.className = 'thinking-text';

        const divider = document.createElement('span');
        divider.className = 'thinking-divider';

        this.currentMessageEl.appendChild(tag);
        this.currentMessageEl.appendChild(thinkingSpan);
        this.currentMessageEl.appendChild(divider);
    }

    // Append text to thinking span
    const thinkingEl = this.currentMessageEl.querySelector('.thinking-text');
    thinkingEl.textContent += text;
    this.scrollToBottom();
}
```

#### Existing behavior preserved

- `appendToMessage()` works unchanged — it appends to `message-content` using `dataset.raw` and `renderContent()`.
- When thinking is active, `appendToThinking()` builds the thinking section. When `debater_finalize` fires, `finalizeMessage()` closes the thinking section. The next `debater_chunk` triggers a new bubble via the existing null-check in `appendToMessage()`.
- For non-reasoning models, no thinking events are emitted. Everything works as before.

#### Download update

In `downloadChat()`, check for `.thinking-text` elements and include them in the exported HTML with a muted style:

```javascript
// Inside the message rendering loop:
const thinkingEl = el.querySelector('.thinking-text');
if (thinkingEl) {
    content = `<div class="thinking-export">💭 ${this.escapeHtml(thinkingEl.textContent)}</div>` + content;
}
```

### static/style.css

Add styles for thinking elements:

```css
/* Thinking mode — uses existing CSS variables for light/dark theme support */
.thinking-tag {
    display: inline-block;
    background: var(--bg-elevated);
    color: var(--ink-muted);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    margin-bottom: 4px;
}

.thinking-text {
    display: block;
    color: var(--ink-muted);
    font-size: 11px;
    line-height: 1.5;
    margin: 4px 0;
}

.thinking-divider {
    display: block;
    border-top: 1px solid var(--border);
    margin: 8px 0;
}
```

Light/dark mode: uses the project's existing CSS variables (`--ink-muted`, `--bg-elevated`, `--border`) which are already defined for both themes.

## Files Changed

| File | Change |
|------|--------|
| `agents.py` | Add `model_settings={'thinking': True}` to two debater agent constructors |
| `debate_engine.py` | Import `ThinkingPart`/`ThinkingPartDelta`, handle in `run_turn()`, emit `thinking_chunk` events |
| `static/app.js` | Add `thinking_chunk` SSE handler, `appendToThinking()` method, update `downloadChat()` |
| `static/style.css` | Add `.thinking-tag`, `.thinking-text`, `.thinking-divider` styles |

## Not Changed

- `main.py` — no new API endpoints
- `config.py` — no new settings
- `models.py` — no model changes
- `tools.py` — no tool changes
- `static/index.html` — no HTML changes

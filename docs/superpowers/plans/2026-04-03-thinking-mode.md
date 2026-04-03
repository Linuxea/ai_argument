# Thinking Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reasoning model support so debaters' thinking process is live-streamed and rendered inline in the chat UI.

**Architecture:** PydanticAI's `model_settings={'thinking': True}` enables thinking on supported models. The engine intercepts `ThinkingPart`/`ThinkingPartDelta` events, emits new `thinking_chunk` SSE events. Frontend renders thinking inline with a smaller-font style. Non-reasoning models are unaffected — thinking is silently ignored.

**Tech Stack:** PydanticAI (thinking support), FastAPI (SSE), vanilla JS (DOM rendering)

**Spec:** `docs/superpowers/specs/2026-04-03-thinking-mode-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `agents.py:135-157` | Modify | Add `model_settings={'thinking': True}` to debater agents |
| `debate_engine.py:1,158-213` | Modify | Import thinking types, handle `ThinkingPart` events in `run_turn()` |
| `tests/conftest.py:33-48` | Modify | Add thinking events to `MockDebateAgent` |
| `tests/test_debate_engine.py` | Modify | Add tests for thinking event emission |
| `tests/test_agents.py` | Modify | Add test verifying `model_settings` on debater agents |
| `static/style.css` | Modify | Add `.thinking-tag`, `.thinking-text`, `.thinking-divider` styles |
| `static/app.js:323-340,467-490` | Modify | Add `thinking_chunk` SSE handler, `appendToThinking()` method |

---

### Task 1: Add `model_settings` to debater agents

**Files:**
- Modify: `agents.py:135-157`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agents.py`:

```python
def test_debater_agent_has_thinking_enabled():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent._model_settings.get("thinking") is True


def test_debater_agent_no_search_has_thinking_enabled():
    from agents import create_debater_agent_no_search
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_debater_agent_no_search("deepseek-chat", "https://api.example.com", "test-key")
    assert agent._model_settings.get("thinking") is True


def test_judge_agent_does_not_have_thinking_enabled():
    with patch("agents._make_model", return_value=_mock_model()):
        agent = create_judge_agent("deepseek-chat", "https://api.example.com", "test-key")
    assert agent._model_settings.get("thinking") is not True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_debater_agent_has_thinking_enabled tests/test_agents.py::test_debater_agent_no_search_has_thinking_enabled -v`
Expected: FAIL — `agent._model_settings` does not contain `thinking`

- [ ] **Step 3: Write minimal implementation**

In `agents.py`, add `model_settings` to both debater agent constructors:

```python
def create_debater_agent(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent with web search capability."""
    from tools import web_search

    agent: Agent[DebaterDeps, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[web_search],
        model_settings={'thinking': True},
    )
    return agent


def create_debater_agent_no_search(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent without web search."""
    agent: Agent[DebaterDeps, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[],
        model_settings={'thinking': True},
    )
    return agent
```

Do NOT modify `create_judge_agent`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: enable thinking mode on debater agents"
```

---

### Task 2: Update mock to support thinking events

**Files:**
- Modify: `tests/conftest.py:33-48`

- [ ] **Step 1: Extend `_MockStreamEvents` to emit thinking events**

Replace the `_MockStreamEvents` class in `tests/conftest.py` with a version that accepts optional thinking text:

```python
class _MockStreamEvents:
    """Mimics the async iterable returned by Agent.run_stream_events()."""

    def __init__(self, text: str, thinking: str = ""):
        self._text = text
        self._thinking = thinking
        self._messages: list[ModelMessage] = []

    async def __aiter__(self):
        # Emit thinking events first, if any
        if self._thinking:
            from pydantic_ai.messages import ThinkingPart, ThinkingPartDelta
            yield PartStartEvent(index=0, part=ThinkingPart(content=self._thinking))
            yield PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=""))

        # Emit text deltas
        words = self._text.split()
        for i, word in enumerate(words):
            delta = word if i == 0 else " " + word
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=delta))

        result = MagicMock()
        result.all_messages.return_value = self._messages
        yield AgentRunResultEvent(result=result)
```

- [ ] **Step 2: Update `MockDebateAgent` to pass thinking through**

Update the `MockDebateAgent` class:

```python
class MockDebateAgent:
    """Mock that replaces both debater_agent and judge_agent for testing."""

    def __init__(self, responses: list[str] = None, thinking: list[str] = None):
        self.responses = responses or ["This is a mock response."]
        self.thinking = thinking or [""] * len(self.responses)
        self.call_count = 0
        self.last_user_prompt = None
        self.last_kwargs = None

    def run_stream_events(self, user_prompt: str, **kwargs):
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        thinking = self.thinking[self.call_count % len(self.thinking)]
        self.call_count += 1
        return _MockStreamEvents(response, thinking=thinking)

    def run_stream(self, user_prompt: str, **kwargs):
        """For judge agent which still uses run_stream()."""
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return _MockRunStreamResult(response)
```

- [ ] **Step 3: Add missing imports in conftest**

At the top of `tests/conftest.py`, update the import to include all needed types:

```python
from pydantic_ai.messages import (
    ModelMessage, PartStartEvent, PartDeltaEvent, TextPartDelta,
    ThinkingPart, ThinkingPartDelta,
)
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `python -m pytest tests/test_debate_engine.py -v`
Expected: ALL PASS — existing tests use default `thinking=[""]`, so no thinking events are emitted.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add thinking event support to mock debate agent"
```

---

### Task 3: Handle thinking events in debate engine

**Files:**
- Modify: `debate_engine.py:1,158-213`
- Test: `tests/test_debate_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_debate_engine.py`:

```python
@pytest.mark.asyncio
async def test_run_turn_emits_thinking_events():
    """When the mock agent returns thinking, thinking_chunk events are emitted."""
    engine, mock = _make_engine(responses=["My argument."])
    mock.thinking = ["Let me analyze this step by step..."]

    debater = Debater(name="Thinker", personality="Deep thinker.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Thinker": []}

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "thinking_chunk" in event_types, f"Got events: {event_types}"

    thinking_events = [e for e in events if e.type == "thinking_chunk"]
    thinking_text = "".join(e.payload["text_chunk"] for e in thinking_events)
    assert "Let me analyze this step by step..." in thinking_text


@pytest.mark.asyncio
async def test_run_turn_thinking_followed_by_finalize():
    """After thinking ends, a debater_finalize event is emitted before text starts."""
    engine, mock = _make_engine(responses=["My argument."])
    mock.thinking = ["Thinking content"]

    debater = Debater(name="Thinker", personality="Deep thinker.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Thinker": []}

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    # debater_finalize should appear between thinking and text
    assert "debater_finalize" in event_types, f"Got events: {event_types}"

    # Find positions
    last_thinking_idx = max(i for i, e in enumerate(events) if e.type == "thinking_chunk")
    first_finalize_after = next(
        i for i, e in enumerate(events)
        if e.type == "debater_finalize" and i > last_thinking_idx
    )
    assert first_finalize_after > last_thinking_idx


@pytest.mark.asyncio
async def test_run_turn_no_thinking_events_without_thinking():
    """When no thinking is returned, no thinking_chunk events are emitted."""
    engine, mock = _make_engine(responses=["Just text, no thinking."])
    # Default thinking=[""] means no ThinkingPart events

    debater = Debater(name="Simple", personality="Simple debater.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Simple": []}

    await engine.run_turn()

    events = []
    while not engine.event_queue.empty():
        events.append(await engine.event_queue.get())

    event_types = [e.type for e in events]
    assert "thinking_chunk" not in event_types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_debate_engine.py::test_run_turn_emits_thinking_events tests/test_debate_engine.py::test_run_turn_thinking_followed_by_finalize -v`
Expected: FAIL — `thinking_chunk` not in event types

- [ ] **Step 3: Add imports to debate_engine.py**

Update the import line at the top of `debate_engine.py`:

```python
from pydantic_ai.messages import (
    ModelMessage, PartStartEvent, PartDeltaEvent,
    TextPart, TextPartDelta,
    ThinkingPart, ThinkingPartDelta,
)
```

- [ ] **Step 4: Add thinking event handling in run_turn()**

In `debate_engine.py`, inside `run_turn()`, add a `_thinking_active` flag before the event loop, and add two new `elif` branches. Also add transition logic to the existing `TextPart` handlers.

The full event loop section becomes (replacing lines ~152-213):

```python
        full_text = ""
        current_query = ""
        result_all_messages = None
        _thinking_active = False

        agent = self.debater_agent if debater.enable_search else self.debater_agent_no_search

        async for event in agent.run_stream_events(
            user_prompt,
            deps=deps,
            message_history=self._history[debater.name],
        ):
            # Handle PartStartEvent — TextPart
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if _thinking_active:
                    _thinking_active = False
                    await self.event_queue.put(Event(type="debater_finalize", payload={}))
                initial_content = event.part.content
                if initial_content:
                    full_text += initial_content
                    await self.event_queue.put(
                        Event(
                            type="debater_chunk",
                            payload={
                                "debater_name": debater.name,
                                "text_chunk": initial_content,
                            },
                        )
                    )
            # Handle PartStartEvent — ThinkingPart
            elif isinstance(event, PartStartEvent) and isinstance(event.part, ThinkingPart):
                _thinking_active = True
                initial = event.part.content
                if initial:
                    await self.event_queue.put(Event(
                        type="thinking_chunk",
                        payload={"debater_name": debater.name, "text_chunk": initial},
                    ))
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                if _thinking_active:
                    _thinking_active = False
                    await self.event_queue.put(Event(type="debater_finalize", payload={}))
                delta = event.delta.content_delta
                full_text += delta
                await self.event_queue.put(
                    Event(
                        type="debater_chunk",
                        payload={
                            "debater_name": debater.name,
                            "text_chunk": delta,
                        },
                    )
                )
            # Handle PartDeltaEvent — ThinkingPartDelta
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, ThinkingPartDelta):
                delta = event.delta.content_delta
                await self.event_queue.put(Event(
                    type="thinking_chunk",
                    payload={"debater_name": debater.name, "text_chunk": delta},
                ))
            elif isinstance(event, FunctionToolCallEvent):
                args = event.part.args
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                current_query = args.get("query", "") if isinstance(args, dict) else ""
                # Finalize current text bubble before showing search card
                await self.event_queue.put(Event(type="debater_finalize", payload={}))
            elif isinstance(event, FunctionToolResultEvent):
                result_text = ""
                if event.result and event.result.content:
                    result_text = str(event.result.content)[:200]
                await self.event_queue.put(Event(
                    type="tool_call",
                    payload={
                        "debater_name": debater.name,
                        "tool_name": "web_search",
                        "query": current_query,
                        "result_summary": result_text,
                    },
                ))
            elif isinstance(event, AgentRunResultEvent):
                result_all_messages = event.result.all_messages()

        # If thinking was the last thing streamed, finalize it
        if _thinking_active:
            await self.event_queue.put(Event(type="debater_finalize", payload={}))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_debate_engine.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add debate_engine.py tests/test_debate_engine.py
git commit -m "feat: handle thinking events in debate engine run_turn"
```

---

### Task 4: Add thinking CSS styles

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Add thinking styles at the end of the file**

Append to `static/style.css`:

```css
/* ═══════════════════════════════════════════════════════════════
   Thinking mode — reasoning model inline thinking display
   ═══════════════════════════════════════════════════════════════ */

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

- [ ] **Step 2: Verify in browser**

Run: `python -m uvicorn main:app --reload --port 8000`

Open the app, start a debate. Verify messages without thinking render identically to before (no visual change).

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "style: add thinking mode CSS styles"
```

---

### Task 5: Add frontend thinking rendering

**Files:**
- Modify: `static/app.js:323-340,467-490`

- [ ] **Step 1: Add `thinking_chunk` SSE handler**

In `static/app.js`, inside `connectSSE()`, add the new handler right after the `debater_start` handler (around line 333):

```javascript
        this.eventSource.addEventListener('thinking_chunk', (e) => {
            const data = this._parseSSEData(e, 'thinking_chunk');
            if (!data) return;
            this.appendToThinking(data.text_chunk);
        });
```

- [ ] **Step 2: Add `appendToThinking` method**

Add this method to the `DebateApp` class, right after the `appendToMessage` method (around line 482):

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

- [ ] **Step 3: Update `downloadChat()` to include thinking**

In the `downloadChat()` method, inside the `msgEls.forEach` loop, after the line that gets `contentEl` (around line 750), add thinking extraction:

```javascript
                // Extract thinking text if present
                const thinkingEl = el.querySelector('.thinking-text');
                let thinkingContent = '';
                if (thinkingEl) {
                    thinkingContent = `<div style="color:${muted};font-size:.82rem;font-style:italic;margin-bottom:8px;padding:6px 10px;background:${bg};border-radius:6px">💭 ${this.escapeHtml(thinkingEl.textContent)}</div>`;
                }
```

Then in the body assembly (around line 763), prepend the thinking content:

Change:
```javascript
                body += `<div class="${cls}">
  <div class="msg-header">...
  <div class="msg-body">${content}</div>
</div>\n`;
```

To:
```javascript
                body += `<div class="${cls}">
  <div class="msg-header">...
  <div class="msg-body">${thinkingContent}${content}</div>
</div>\n`;
```

- [ ] **Step 4: Manual test with a reasoning model**

1. Run: `python -m uvicorn main:app --reload --port 8000`
2. Set API to a reasoning model (e.g. `deepseek-reasoner` on DeepSeek API)
3. Start a debate
4. Verify: debater messages show "💭 thinking" tag with smaller-font thinking text, then a divider line, then the reply
5. Verify: download includes thinking content in the exported HTML

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: render thinking content inline in chat messages"
```

---

### Task 6: Final integration test

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Manual integration test with non-reasoning model**

1. Set API to `deepseek-chat` (non-reasoning model)
2. Start a debate
3. Verify: messages render normally, no thinking tag, no visual change from before

- [ ] **Step 3: Manual integration test with reasoning model**

1. Set API to `deepseek-reasoner` (reasoning model)
2. Start a debate
3. Verify: thinking streams live with smaller font
4. Verify: reply text appears after thinking with normal font
5. Verify: download includes thinking in exported HTML
6. Verify: judge does NOT show thinking

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration fixes for thinking mode"
```

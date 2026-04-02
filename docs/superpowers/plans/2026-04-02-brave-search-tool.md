# Brave Search Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Brave Search web search tool to debater agents so LLMs can look up facts during debates, with frontend search cards displayed as distinct bubbles.

**Architecture:** Register an `async def web_search()` tool on the debater agent via PydanticAI's tool mechanism. Use `event_stream_handler` in `run_stream()` to detect tool calls and emit `tool_call` SSE events. Frontend renders search cards between normal text bubbles using a multi-bubble flow.

**Tech Stack:** PydanticAI tools, httpx (Brave Search API), Server-Sent Events, vanilla JS

**Spec:** `docs/superpowers/specs/2026-04-02-brave-search-tool-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `tools.py` | **Create** | `web_search()` tool function calling Brave Search API |
| `tests/test_tools.py` | **Create** | Unit tests for `web_search()` with mocked HTTP |
| `agents.py` | **Modify** | Register tool on debater agent, add `brave_api_key` to `DebaterDeps` |
| `config.py` | **Modify** | Add `brave_api_key` to `Settings` |
| `debate_engine.py` | **Modify** | Pass API key through deps, add `event_stream_handler` for tool events |
| `main.py` | **Modify** | Pass `brave_api_key` from settings to `DebateEngine` |
| `static/app.js` | **Modify** | Handle `tool_call` SSE event, `addToolCard()`, multi-bubble support |
| `static/style.css` | **Modify** | Search card styles (dashed border, muted colors) |
| `tests/test_agents.py` | **Modify** | Update `DebaterDeps` tests for new field, verify tool registration |
| `tests/test_debate_engine.py` | **Modify** | Test tool_call SSE event emission |
| `tests/conftest.py` | **Modify** | Update `MockDebateAgent` to support `event_stream_handler` |

---

### Task 1: Add `brave_api_key` to Settings and DebaterDeps

**Files:**
- Modify: `config.py:17-28`
- Modify: `agents.py:43-50`
- Modify: `tests/test_agents.py:83-94`

- [ ] **Step 1: Write the failing test**

Add a test for the new `brave_api_key` field in `tests/test_agents.py`:

```python
def test_debater_deps_with_brave_api_key():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(
        topic="AI ethics",
        debater=debater,
        round_number=1,
        max_rounds=5,
        brave_api_key="test-key-123",
    )
    assert deps.brave_api_key == "test-key-123"


def test_debater_deps_brave_api_key_defaults_none():
    debater = Debater(name="Test", personality="Test.")
    deps = DebaterDeps(
        topic="AI ethics",
        debater=debater,
        round_number=1,
        max_rounds=5,
    )
    assert deps.brave_api_key is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_debater_deps_with_brave_api_key -v`
Expected: FAIL — `DebaterDeps.__init__()` got an unexpected keyword argument `brave_api_key`

- [ ] **Step 3: Add `brave_api_key` to `DebaterDeps`**

In `agents.py`, add the field:

```python
@dataclass
class DebaterDeps:
    """Dependencies injected into each debater agent run."""

    topic: str
    debater: Debater
    round_number: int
    max_rounds: int | None
    brave_api_key: str | None = None
```

- [ ] **Step 4: Add `brave_api_key` to `Settings`**

In `config.py`, add to `__init__`:

```python
class Settings:
    def __init__(
        self,
        api_base_url: str = "https://api.deepseek.com",
        api_key: str = None,
        model: str = "deepseek-chat",
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model
        self.brave_api_key = os.environ.get("BRAVE_API_KEY", "")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add agents.py config.py tests/test_agents.py
git commit -m "feat: add brave_api_key to DebaterDeps and Settings"
```

---

### Task 2: Create `tools.py` with `web_search` (TDD)

**Files:**
- Create: `tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tools.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tools import web_search
from agents import DebaterDeps
from models import Debater


def _make_ctx(api_key: str = "test-key") -> MagicMock:
    """Create a mock RunContext with DebaterDeps."""
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="Test topic",
        debater=Debater(name="Test", personality="Test."),
        round_number=0,
        max_rounds=None,
        brave_api_key=api_key,
    )
    return ctx


@pytest.mark.asyncio
async def test_web_search_returns_no_key_message():
    ctx = _make_ctx(api_key=None)
    result = await web_search(ctx, "solar energy")
    assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_web_search_returns_results():
    ctx = _make_ctx(api_key="valid-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "Solar Power", "description": "Solar costs dropped 89%."},
                {"title": "Wind Energy", "description": "Wind is cheaper than coal."},
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "renewable energy cost")

    assert "renewable energy cost" in result
    assert "Solar Power" in result
    assert "Wind Energy" in result


@pytest.mark.asyncio
async def test_web_search_returns_no_results():
    ctx = _make_ctx(api_key="valid-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"web": {"results": []}}
    mock_response.raise_for_status = MagicMock()

    with patch("tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "obscure topic xyz")

    assert "No results found" in result


@pytest.mark.asyncio
async def test_web_search_handles_api_error():
    ctx = _make_ctx(api_key="valid-key")

    import httpx

    with patch("tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.HTTPStatusError(
            "Rate limited",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "anything")

    assert "error" in result.lower() or "failed" in result.lower()


@pytest.mark.asyncio
async def test_web_search_truncates_long_results():
    ctx = _make_ctx(api_key="valid-key")

    # Create many long results
    long_results = [
        {"title": f"Result {i}", "description": "X" * 300}
        for i in range(20)
    ]

    mock_response = MagicMock()
    mock_response.json.return_value = {"web": {"results": long_results}}
    mock_response.raise_for_status = MagicMock()

    with patch("tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "long topic")

    # Result should be truncated to MAX_TOTAL_CHARS
    assert len(result) < 10000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Create `tools.py`**

Create `tools.py`:

```python
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
    api_key = ctx.deps.brave_api_key
    if not api_key:
        return "Search is not configured (no API key). Proceed without search results."

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                BRAVE_ENDPOINT,
                headers={"X-Subscription-Token": api_key},
                params={"q": query, "count": MAX_RESULTS},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        return f"Search failed: {e}. Proceed without search results."

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

- [ ] **Step 4: Install httpx**

Run: `pip install httpx`

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_tools.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add tools.py tests/test_tools.py
git commit -m "feat: add web_search tool with Brave Search API"
```

---

### Task 3: Register search tool on debater agent

**Files:**
- Modify: `agents.py:53-61`
- Modify: `tests/test_agents.py:16-18`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agents.py`:

```python
def test_debater_agent_has_web_search_tool():
    agent = create_debater_agent("deepseek:deepseek-chat")
    tool_names = [t.name for t in agent._toolset._tools.values()]
    assert "web_search" in tool_names


def test_judge_agent_has_no_web_search_tool():
    agent = create_judge_agent("deepseek:deepseek-chat")
    # Judge agent should have no tools at all
    tool_names = [t.name for t in agent._toolset._tools.values()]
    assert "web_search" not in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_debater_agent_has_web_search_tool -v`
Expected: FAIL — `web_search` not in tool names

- [ ] **Step 3: Register tool on debater agent**

In `agents.py`, add import and register:

```python
from tools import web_search


def create_debater_agent(model: str) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent configured for debate participants."""
    agent: Agent[DebaterDeps, str] = Agent(
        model,
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[web_search],
    )
    return agent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: register web_search tool on debater agent"
```

---

### Task 4: Update DebateEngine to pass API key and handle tool events

**Files:**
- Modify: `debate_engine.py:48-56,114-171`
- Modify: `tests/conftest.py`
- Modify: `tests/test_debate_engine.py`

- [ ] **Step 1: Update `DebateEngine.__init__` to accept `brave_api_key`**

In `debate_engine.py`, change the constructor:

```python
def __init__(self, model: str, brave_api_key: str = ""):
    self.model = model
    self.brave_api_key = brave_api_key
    self.debater_agent = create_debater_agent(model)
    self.judge_agent = create_judge_agent(model)
    self.state: Optional[DebateState] = None
    self.event_queue: asyncio.Queue = asyncio.Queue()
    self._loop_task: Optional[asyncio.Task] = None
    self._history: dict[str, list[ModelMessage]] = {}
```

- [ ] **Step 2: Add imports for event stream types**

At the top of `debate_engine.py`, add:

```python
from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
```

- [ ] **Step 3: Pass `brave_api_key` through deps in `run_turn`**

In `debate_engine.py`, update `run_turn()` where deps is constructed (around line 121):

```python
deps = DebaterDeps(
    topic=self.state.topic,
    debater=debater,
    round_number=self.state.current_round,
    max_rounds=self.state.max_rounds,
    brave_api_key=self.brave_api_key,
)
```

- [ ] **Step 4: Add `_handle_events` method to `DebateEngine`**

Add this method to `DebateEngine` class:

```python
async def _handle_events(self, ctx, event_stream, debater_name: str):
    """Monitor agent execution, emit SSE events for tool calls."""
    current_query = ""

    async for event in event_stream:
        if isinstance(event, FunctionToolCallEvent):
            current_query = event.part.args.get("query", "")
        elif isinstance(event, FunctionToolResultEvent):
            result_text = ""
            if event.result and event.result.content:
                result_text = str(event.result.content)[:200]
            await self.event_queue.put(
                Event(
                    type="tool_call",
                    payload={
                        "debater_name": debater_name,
                        "tool_name": "web_search",
                        "query": current_query,
                        "result_summary": result_text,
                    },
                )
            )
```

- [ ] **Step 5: Wire `event_stream_handler` into `run_stream` call**

In `run_turn()`, update the `run_stream` call to include the handler:

```python
full_text = ""
async with self.debater_agent.run_stream(
    user_prompt,
    deps=deps,
    message_history=self._history[debater.name],
    event_stream_handler=lambda ctx, es: self._handle_events(
        ctx, es, debater.name
    ),
) as result:
    async for delta in result.stream_text(delta=True):
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
```

- [ ] **Step 6: Update `main.py` to pass `brave_api_key`**

In `main.py`, update the lifespan function and `update_settings`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global debate_engine
    model = build_model_string(settings.api_base_url, settings.model)
    debate_engine = DebateEngine(model=model, brave_api_key=settings.brave_api_key)
    yield
```

In `update_settings()`, after model update, also update brave key if needed (no UI for this — it's env-var only, so just make sure the engine gets it at creation time).

- [ ] **Step 7: Update `conftest.py` MockDebateAgent to accept event_stream_handler**

Update `MockDebateAgent.run_stream` in `tests/conftest.py`:

```python
class MockStreamResult:
    """Mimics the async context manager returned by Agent.run_stream()."""

    def __init__(self, text: str):
        self._text = text
        self._messages: list[ModelMessage] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def stream_text(self, delta=True):
        words = self._text.split()
        for i, word in enumerate(words):
            if delta:
                yield word if i == 0 else " " + word
            else:
                yield " ".join(words[: i + 1])

    def all_messages(self) -> list[ModelMessage]:
        return self._messages


class MockDebateAgent:
    """Mock that replaces both debater_agent and judge_agent for testing."""

    def __init__(self, responses: list[str] = None):
        self.responses = responses or ["This is a mock response."]
        self.call_count = 0
        self.last_user_prompt = None
        self.last_kwargs = None

    def run_stream(self, user_prompt: str, **kwargs):
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MockStreamResult(response)
```

- [ ] **Step 8: Write test for tool_call SSE event**

Add to `tests/test_debate_engine.py`:

```python
@pytest.mark.asyncio
async def test_run_turn_passes_brave_api_key_in_deps():
    engine, mock = _make_engine(responses=["I searched and found..."])
    engine.brave_api_key = "test-brave-key"

    debater = Debater(name="Alice", personality="You are Alice.")
    engine.state = DebateState(topic="Test topic", debaters=[debater])
    engine._history = {"Alice": []}

    await engine.run_turn()

    # Check the deps passed to the agent include the API key
    deps = mock.last_kwargs.get("deps")
    assert deps is not None
    assert deps.brave_api_key == "test-brave-key"


def test_engine_stores_brave_api_key():
    engine, _ = _make_engine()
    engine.brave_api_key = "my-key"
    assert engine.brave_api_key == "my-key"
```

- [ ] **Step 9: Update `_make_engine` helper for new constructor signature**

In `tests/test_debate_engine.py`, the `_make_engine` helper creates engine via `object.__new__()`, so it bypasses `__init__`. Add `brave_api_key` initialization:

```python
def _make_engine(responses=None):
    """Create a DebateEngine with mocked agents."""
    import asyncio

    mock = MockDebateAgent(responses=responses)
    engine = object.__new__(DebateEngine)
    engine.model = "test:model"
    engine.brave_api_key = ""
    engine.debater_agent = mock
    engine.judge_agent = MockDebateAgent(responses=responses or ["Judgment."])
    engine.state = None
    engine.event_queue = asyncio.Queue()
    engine._loop_task = None
    engine._history = {}
    return engine, mock
```

- [ ] **Step 10: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 11: Commit**

```bash
git add debate_engine.py main.py tests/conftest.py tests/test_debate_engine.py
git commit -m "feat: wire Brave Search API key through DebateEngine and deps"
```

---

### Task 5: Add `tool_call` SSE event handler in frontend

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Track current debater info**

In `app.js`, inside the `debater_start` SSE handler, save the debater info so it can be reused after tool calls:

```javascript
this.eventSource.addEventListener('debater_start', (e) => {
    const data = JSON.parse(e.data);
    // Save for reuse in multi-bubble flow after tool calls
    this._currentDebaterName = data.debater_name;
    this._currentDebaterColor = data.color;
    this._currentDebaterAvatar = data.avatar;
    this.createMessage(data.debater_name, data.color, data.avatar, 'debater');
});
```

- [ ] **Step 2: Update `appendToMessage` to create bubble if needed**

Replace the existing `appendToMessage` method:

```javascript
appendToMessage(text) {
    if (!this.currentMessageEl) {
        // No active bubble — create one for the same debater
        // (happens after a tool_call event finalized the previous bubble)
        this.createMessage(
            this._currentDebaterName || 'Unknown',
            this._currentDebaterColor || '#333333',
            this._currentDebaterAvatar || '💬',
            'debater'
        );
    }
    const raw = (this.currentMessageEl.dataset.raw || '') + text;
    this.currentMessageEl.dataset.raw = raw;
    this.currentMessageEl.innerHTML = this.renderContent(raw);
    this.scrollToBottom();
}
```

- [ ] **Step 3: Add `tool_call` SSE event listener**

In the `connectSSE()` method, add after the `debater_end` listener:

```javascript
this.eventSource.addEventListener('tool_call', (e) => {
    const data = JSON.parse(e.data);
    // Finalize current text bubble (if any)
    this.finalizeMessage();
    // Render search card
    this.addToolCard(data.debater_name, data.query, data.result_summary);
});
```

- [ ] **Step 4: Add `addToolCard` method**

Add this method to `DebateApp`:

```javascript
addToolCard(debaterName, query, resultSummary) {
    const message = document.createElement('div');
    message.className = 'message ai tool-card';

    const header = document.createElement('div');
    header.className = 'message-header';

    const avatarEl = document.createElement('span');
    avatarEl.className = 'message-avatar';
    avatarEl.textContent = this._currentDebaterAvatar || '🔍';

    const senderEl = document.createElement('span');
    senderEl.className = 'message-sender';
    senderEl.style.color = this.sanitizeColor(this._currentDebaterColor || '#333333');
    senderEl.textContent = debaterName;

    const timeEl = document.createElement('span');
    timeEl.className = 'message-time';
    timeEl.textContent = new Date().toLocaleTimeString();

    header.appendChild(avatarEl);
    header.appendChild(senderEl);
    header.appendChild(timeEl);

    const content = document.createElement('div');
    content.className = 'tool-card-content';

    const label = document.createElement('div');
    label.className = 'tool-card-label';
    label.textContent = '🔍 Searched: ' + query;

    const results = document.createElement('div');
    results.className = 'tool-card-results';
    results.innerHTML = this.renderContent(resultSummary || '');

    content.appendChild(label);
    content.appendChild(results);

    message.appendChild(header);
    message.appendChild(content);
    this.messages.appendChild(message);
    this.scrollToBottom();
}
```

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: add tool_call SSE handler and multi-bubble frontend support"
```

---

### Task 6: Add search card CSS styles

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Add tool card styles**

Append to the end of `static/style.css` (before the responsive section, after the loading dots section):

```css
/* ─── Tool Call Cards ──────────────────────────────── */

.tool-card .tool-card-content {
    background: var(--bg-input);
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    border: 1px dashed var(--border);
    line-height: 1.5;
    word-wrap: break-word;
    font-size: 0.82rem;
    color: var(--text-soft);
}

.tool-card .tool-card-label {
    font-weight: 600;
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-bottom: 6px;
}

.tool-card .tool-card-results {
    font-size: 0.82rem;
    color: var(--text-soft);
}

.tool-card .tool-card-results p {
    margin: 0;
}

.tool-card .tool-card-results ul,
.tool-card .tool-card-results ol {
    padding-left: 18px;
    margin: 4px 0;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: add search card CSS styles"
```

---

### Task 7: Update download feature to include tool cards

**Files:**
- Modify: `static/app.js` — `downloadChat()` method

- [ ] **Step 1: Update the download loop to handle tool cards**

In `downloadChat()`, update the `msgEls.forEach` block. The existing code already handles `.ai` messages, so tool cards (which also have `.ai` and `.tool-card` classes) will be captured. But we want different styling. Update the body-building loop:

Find the existing block:

```javascript
const isUser = el.classList.contains('user');
const cls = isUser ? 'user-msg' : 'debater-msg';
```

Replace with:

```javascript
const isUser = el.classList.contains('user');
const isToolCard = el.classList.contains('tool-card');
const cls = isUser ? 'user-msg' : (isToolCard ? 'tool-msg' : 'debater-msg');
```

And add a new CSS rule for `.tool-msg` in the download HTML template:

```javascript
.sys-msg{text-align:center;color:${muted};font-style:italic;font-size:.84rem;margin:12px 0}
.sys-msg::before,.sys-msg::after{content:' — ';color:${border}}
.tool-msg .msg-body{border-left:1px dashed ${border};background:${bg};font-size:.85rem;color:${muted}}
```

Append this after the `.sys-msg` rule inside the `<style>` block of the download HTML.

- [ ] **Step 2: Commit**

```bash
git add static/app.js
git commit -m "feat: include tool cards in debate download"
```

---

### Task 8: End-to-end verification

**Files:**
- No new files

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS (except the 2 known failures in test_config.py and test_main.py mentioned in CLAUDE.md)

- [ ] **Step 2: Start the server and verify manually**

Run: `python -m uvicorn main:app --reload --port 8000`

Manual test checklist:
1. Open `http://localhost:8000` in browser
2. Start a debate with a topic that might trigger search (e.g., "Is AI regulation necessary in 2025?")
3. Verify that if a debater uses search, a dashed-border card appears between text bubbles
4. Verify that the debate continues normally after search
5. Verify download includes tool cards
6. Verify that without `BRAVE_API_KEY`, debate still works (no crash)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Brave Search tool integration complete"
```

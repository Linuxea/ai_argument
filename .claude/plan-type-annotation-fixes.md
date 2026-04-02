# Fix Plan: Python Type Annotation & Static Analysis Warnings

## Already Fixed

- [x] `config.py:23` — `api_key: str = None` → `api_key: str | None = None`

---

## Priority 1: Type Annotation Mismatches (will cause pyright/pylance errors)

### 1.1 `main.py:16` — None assigned to non-optional type
```python
# Before
debate_engine: DebateEngine = None
# After
debate_engine: DebateEngine | None = None
```
**Impact:** This propagates — every access to `debate_engine` in main.py already has `if debate_engine` guards, so the fix is safe.

### 1.2 `debate_engine.py:55` — Optional uses old syntax
```python
# Before
self.state: Optional[DebateState] = None
# After
self.state: DebateState | None = None
```
Also line 57:
```python
# Before
self._loop_task: Optional[asyncio.Task] = None
# After
self._loop_task: asyncio.Task[None] | None = None
```
And remove `from typing import Optional` import (line 4) since it's no longer needed.

### 1.3 `models.py:24` — Optional uses old syntax
```python
# Before
max_rounds: Optional[int] = None
# After
max_rounds: int | None = None
```
Update import: `from typing import Optional, Literal` → `from typing import Literal` (remove `Optional`).

### 1.4 `debate_engine.py:26` — Optional in dataclass
```python
# Before
max_rounds: Optional[int] = None
# After
max_rounds: int | None = None
```

### 1.5 `debate_engine.py:59` — Optional in method parameter
```python
# Before
def start(self, topic: str, debaters: list[Debater], max_rounds: Optional[int] = None):
# After
def start(self, topic: str, debaters: list[Debater], max_rounds: int | None = None) -> None:
```

### 1.6 `tests/conftest.py:8` — None assigned to non-optional list
```python
# Before
def __init__(self, responses: list[str] = None):
# After
def __init__(self, responses: list[str] | None = None) -> None:
```

---

## Priority 2: Import & Style Consistency

### 2.1 `models.py:15` — Import inside method body
```python
# Before (inside validate_color)
import re
# After — move to top of file
import re  # at line 1
```
**Impact:** `re` is a stdlib module, the import is cached by Python after first load, so this is minor. But it's still cleaner at module level.

### 2.2 `debate_engine.py:4` — Remove unused `Optional` import
After replacing all `Optional[X]` with `X | None`, remove `from typing import Optional`.

### 2.3 `models.py:2` — Remove unused `Optional` import
Same — after replacing, update to `from typing import Literal`.

---

## Priority 3: Missing Return Type Annotations

These don't cause errors but are flagged by strict type checkers. Adding them is low-risk, high-consistency.

### 3.1 `llm_client.py:9`
```python
def __init__(self, base_url: str, api_key: str, model: str) -> None:
```

### 3.2 `debate_engine.py` — multiple methods
Add `-> None` to: `__init__`, `start`, `ensure_loop_running`, `_advance_turn`, `stop`, `resume`, `inject_message`
Add `-> bool` to: `stop` (already returns bool), `resume`, `inject_message`, `judge`
Add `-> list[dict]` to: `build_messages` (already correct)

### 3.3 `tests/conftest.py:13`
```python
async def stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
```
Needs `from typing import AsyncGenerator` import.

---

## Priority 4: Defensive Coding (optional)

### 4.1 `config.py:12-14` — yaml.safe_load can return None
```python
# Before
data = yaml.safe_load(f)
return [Debater(**d) for d in data["debaters"]]
# After
data = yaml.safe_load(f) or {}
return [Debater(**d) for d in data.get("debaters", [])]
```
**Risk:** Very low — presets.yaml exists and is valid. But defensive coding is good practice.

### 4.2 `main.py:177` — debate_engine could be None in update_settings
```python
# Before
debate_engine.llm = LLMClient(...)
# After — add guard
if debate_engine is not None:
    debate_engine.llm = LLMClient(...)
```
**Risk:** In practice, `lifespan` always runs before endpoints, so this can't be None. But strict mode flags it.

---

## NOT fixing (by design)

| Item | Reason |
|------|--------|
| `main.py:161` broad `except Exception` | Catching all exceptions for user-facing error messages is acceptable here |
| `llm_client.py:27` broad `except Exception` | Purposefully catches API errors and yields them as text to frontend |
| Mutable globals in `main.py` | Intentional for single-user app (documented in CLAUDE.md) |
| Missing `-> None` on test functions | Low value, pure test code |
| `main.py` endpoint return types | FastAPI infers these from `response_class` and actual returns |

---

## Execution Order

1. Priority 1 (all type mismatches) — 6 edits across 4 files
2. Priority 2 (import cleanup) — 3 edits, follow Priority 1
3. Priority 3 (return types) — 10+ edits, optional
4. Priority 4 (defensive) — 2 edits, optional

Total estimated changes: ~21 edits across 5 files (Priority 1-2), or ~31 edits (all priorities).

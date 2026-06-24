"""Prompt content loader.

Prompt text lives in ``prompts/*.md`` at the repo root, outside the Python
package, so content can be iterated on without touching code (no ruff/
coverage/test cycle). Loaded once at import; a missing file fails loudly.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load ``prompts/<name>.md`` as UTF-8 text."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")

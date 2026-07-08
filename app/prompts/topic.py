"""Topic prompts (loaded from prompts/*.md)."""

from __future__ import annotations

from app.prompts.loader import load_prompt

TOPIC_REFINE_PROMPT = load_prompt("topic_refine")
TOPIC_SUGGEST_PROMPT = load_prompt("topic_suggest")

"""Debater system + user prompt assembly (zero PydanticAI dependency).

The system prompt is intentionally **stable across all rounds** for a given
debater (byte-identical) so the ``[system]`` segment is prefix-cacheable on
OpenAI-compatible providers (DeepSeek/OpenAI cache the longest stable prefix).
All round-dependent context (countdown, opening-search guidance) lives in the
user prompt instead.
"""

from __future__ import annotations

from datetime import datetime

from app.prompts.loader import load_prompt
from app.prompts.stances import STANCE_INSTRUCTIONS

DEBATE_RULES = load_prompt("debate_rules")
STRATEGY_INSTRUCTIONS = load_prompt("strategy_instructions")
MEMORY_INSTRUCTIONS = load_prompt("memory_instructions")
SEARCH_INSTRUCTIONS = load_prompt("search_instructions")

_CHARACTER_FRAME = (
    "## Your Character (HIGHEST priority for voice and tone)\n"
    "Stay fully in character at all times — it defines your personality, "
    "tone, vocabulary, humor, and rhetorical style. This OVERRIDES ALL "
    "style, tone, and argumentation guidance above whenever there is a "
    "conflict: your character's voice always wins. Structural rules still "
    "apply: keep responses 80-200 words, use [[Name]] mentions to refer to "
    "others, no headers or section labels.\n\n"
    "{personality}"
)


def _date_context() -> str:
    now = datetime.now()
    return (
        f"**CURRENT DATE: {now.strftime('%Y-%m-%d')}**. "
        f"'Recent'/'current' means {now.year}; pre-{now.year} info may be outdated."
    )


def build_debater_system_prompt(deps) -> str:
    """Build the debater system prompt from deps.

    Stable across rounds: depends only on ``deps.debater`` (stance,
    personality, enable_search) — never on ``round_number`` or ``max_rounds``.
    """
    debater = deps.debater
    stance = STANCE_INSTRUCTIONS.get(debater.stance, STANCE_INSTRUCTIONS["中立"])

    parts = [
        _date_context(),
        DEBATE_RULES,
        STRATEGY_INSTRUCTIONS,
        MEMORY_INSTRUCTIONS,
        f"Your stance: {stance}",
        _CHARACTER_FRAME.format(personality=debater.personality),
    ]

    if debater.enable_search:
        parts.append(SEARCH_INSTRUCTIONS)

    return "\n\n---\n\n".join(parts)

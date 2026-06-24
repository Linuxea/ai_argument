"""Debater system + user prompt assembly (zero PydanticAI dependency).

The system prompt is intentionally **stable across all rounds** for a given
debater (byte-identical) so the ``[system]`` segment is prefix-cacheable on
OpenAI-compatible providers (DeepSeek/OpenAI cache the longest stable prefix).
All round-dependent context (countdown, opening-search guidance) lives in the
user prompt instead.
"""

from __future__ import annotations

from datetime import datetime

from app.engine.state import DebateState
from app.models import Debater
from app.prompts.defense import (
    TOPIC_CLOSE,
    TOPIC_NOTE,
    TOPIC_OPEN,
    USER_MSG_CLOSE,
    USER_MSG_NOTE,
    USER_MSG_OPEN,
)
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


def build_debater_user_prompt(state: DebateState, debater: Debater) -> str:
    """Build the user prompt for ``debater``'s next turn.

    The debater's own past messages are excluded — they're already in
    ``message_history`` as prior ``ModelResponse`` entries managed by
    PydanticAI, so restating them would double-count. Round-dependent context
    (countdown, opening-search guidance) lives here so the system prompt stays
    cache-stable.
    """
    parts: list[str] = []

    if not state.history:
        parts.append(
            "You are the first speaker. "
            "No one has spoken yet - do NOT reference or quote anyone. "
            "Present your opening argument on the topic below. " + TOPIC_NOTE
        )
        parts.append(f"{TOPIC_OPEN}{state.topic}{TOPIC_CLOSE}")
    else:
        parts.append("Debate topic (" + TOPIC_NOTE + "):")
        parts.append(f"{TOPIC_OPEN}{state.topic}{TOPIC_CLOSE}")
        parts.append(USER_MSG_NOTE)

        if state.argument_summaries:
            summary_lines = ["[Key arguments raised so far]:"]
            for s in state.argument_summaries:
                points_text = "; ".join(s.points)
                summary_lines.append(f"Round {s.round + 1} - {s.debater_name}: {points_text}")
            parts.append("\n".join(summary_lines))

        for msg in state.history:
            if msg.speaker == debater.name:
                continue
            if msg.speaker == "You":
                parts.append(f"[You]: {USER_MSG_OPEN}{msg.content}{USER_MSG_CLOSE}")
            else:
                parts.append(f"[{msg.speaker}]: {msg.content}")

    _append_round_context(parts, state, debater)
    return "\n\n".join(parts)


def _append_round_context(parts: list[str], state: DebateState, debater: Debater) -> None:
    """Append round countdown (when bounded) and opening-search guidance (round 0)."""
    current = state.current_round + 1

    if state.max_rounds is not None:
        remaining = state.max_rounds - state.current_round
        if remaining <= 1:
            parts.append(
                f"This is round {current} of {state.max_rounds} - "
                "FINAL ROUND. Make your strongest closing argument. No holding back."
            )
        else:
            plural = "s" if remaining - 1 != 1 else ""
            parts.append(
                f"This is round {current} of {state.max_rounds}. "
                f"There {'is' if remaining - 1 == 1 else 'are'} {remaining - 1} "
                f"round{plural} remaining after this one."
            )

    if state.current_round == 0 and debater.enable_search:
        parts.append(
            "This is your opening round: you may search 2-4 times to gather "
            "supporting evidence before presenting your argument."
        )

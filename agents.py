"""Compatibility shim — real implementation now lives in :mod:`app.agents`.

Kept so existing ``from agents import ...`` imports keep working during the
staged refactor. Removed in stage 6.
"""
from app.agents import (  # noqa: F401
    CONCESSION_INSTRUCTIONS,
    DEBATE_RULES,
    DebaterDeps,
    EXTRACT_POINTS_PROMPT,
    JUDGE_PROMPT,
    MEMORY_INSTRUCTIONS,
    SEARCH_INSTRUCTIONS,
    STANCE_INSTRUCTIONS,
    STRATEGY_INSTRUCTIONS,
    _build_debater_instructions,
    _make_model,
    create_debater_agent,
    create_extractor_agent,
    create_judge_agent,
)

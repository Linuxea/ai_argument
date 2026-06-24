"""Prompt assembly package (zero PydanticAI dependency).

Public API for the prompt layer. ``app/agents.py`` and ``app/engine/debate.py``
import from here; prompt content lives in ``prompts/*.md`` loaded by
``app.prompts.loader``.
"""

from __future__ import annotations

from app.prompts.debater import build_debater_system_prompt, build_debater_user_prompt
from app.prompts.extract import EXTRACT_POINTS_PROMPT
from app.prompts.judge import JUDGE_SYSTEM_PROMPT, build_judge_transcript
from app.prompts.topic import TOPIC_REFINE_PROMPT

__all__ = [
    "EXTRACT_POINTS_PROMPT",
    "JUDGE_SYSTEM_PROMPT",
    "TOPIC_REFINE_PROMPT",
    "build_debater_system_prompt",
    "build_debater_user_prompt",
    "build_judge_transcript",
]

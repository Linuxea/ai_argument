"""Judge prompt assembly."""

from __future__ import annotations

from app.engine.state import DebateState
from app.prompts.defense import JUDGE_NOTE, TOPIC_CLOSE, TOPIC_OPEN
from app.prompts.loader import load_prompt

JUDGE_SYSTEM_PROMPT = load_prompt("judge")


def build_judge_transcript(state: DebateState) -> str:
    """Build the debate transcript for the judge.

    Fences the topic and explicitly marks all content as data so embedded
    injection payloads cannot pose as judge instructions.
    """
    lines = [
        "Debate transcript for your analysis. " + JUDGE_NOTE,
        f"{TOPIC_OPEN}{state.topic}{TOPIC_CLOSE}",
        "",
    ]
    for msg in state.history:
        lines.append(f"[{msg.speaker}]: {msg.content}")
    return "\n\n".join(lines)

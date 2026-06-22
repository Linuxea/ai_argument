"""Pydantic models for API contracts plus the ArgumentSummary data class."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Bounded to keep prompts/context windows sane for a single-user tool.
MAX_TOPIC_LENGTH = 500
MAX_MESSAGE_LENGTH = 2000
MAX_PERSONALITY_LENGTH = 1000
MAX_NAME_LENGTH = 50
MAX_AVATAR_LENGTH = 10
MAX_DEBATERS = 20
MAX_ROUNDS = 50

# Centralised stance vocabulary. Used by Debater, CustomDebaterRequest and
# STANCE_INSTRUCTIONS in app.agents — keep all three in sync via this alias.
Stance = Literal["正方", "反方", "中立"]


def _validate_color(v: str) -> str:
    if not re.match(r"^#[0-9a-fA-F]{6}$", v):
        raise ValueError("color must be a 6-digit hex color (e.g. #ff6600)")
    return v


class Debater(BaseModel):
    name: str = Field(max_length=MAX_NAME_LENGTH)
    color: str = "#333333"
    avatar: str = Field(default="💬", max_length=MAX_AVATAR_LENGTH)
    stance: Stance = "中立"
    personality: str = Field(max_length=MAX_PERSONALITY_LENGTH)
    enable_search: bool = True

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_color(v)


class DebateConfig(BaseModel):
    topic: str = Field(max_length=MAX_TOPIC_LENGTH)
    debater_names: list[str] = Field(min_length=2, max_length=MAX_DEBATERS)
    max_rounds: int | None = Field(default=None, ge=1, le=MAX_ROUNDS)

    @field_validator("debater_names")
    @classmethod
    def validate_debater_names(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("debater_names must not contain duplicates")
        return v


class UserMessage(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_LENGTH)


class CustomDebaterRequest(Debater):
    """Custom debater creation payload.

    Inherits every field and validator (including the hex-color check) from
    ``Debater`` so the request and internal schemas cannot drift apart. The
    separate name lets the route layer evolve the request schema (e.g. add
    captcha, honeypot) without touching the internal model.
    """


class RefineTopicRequest(BaseModel):
    topic: str = Field(max_length=MAX_TOPIC_LENGTH)


@dataclass
class ArgumentSummary:
    round: int
    debater_name: str
    points: list[str] = field(default_factory=list)

"""Pydantic models for API contracts plus the ArgumentSummary data class."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class Debater(BaseModel):
    name: str
    color: str = "#333333"
    avatar: str = "💬"
    stance: Literal["正方", "反方", "中立"] = "中立"
    personality: str
    enable_search: bool = True

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("color must be a 6-digit hex color (e.g. #ff6600)")
        return v


class DebateConfig(BaseModel):
    topic: str
    debater_names: list[str]
    max_rounds: int | None = None


class UserMessage(BaseModel):
    message: str


class CustomDebaterRequest(BaseModel):
    name: str
    color: str = "#333333"
    avatar: str = "💬"
    stance: Literal["正方", "反方", "中立"] = "中立"
    personality: str
    enable_search: bool = True


class RefineTopicRequest(BaseModel):
    topic: str


@dataclass
class ArgumentSummary:
    round: int
    debater_name: str
    points: list[str] = field(default_factory=list)

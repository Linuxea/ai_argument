from pydantic import BaseModel, field_validator
from typing import Optional, Literal


class Debater(BaseModel):
    name: str
    color: str = "#333333"
    avatar: str = "💬"
    stance: Literal["for", "against", "neutral"] = "neutral"
    personality: str
    enable_search: bool = True

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        import re
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("color must be a 6-digit hex color (e.g. #ff6600)")
        return v


class DebateConfig(BaseModel):
    topic: str
    debater_names: list[str]
    max_rounds: Optional[int] = None


class UserMessage(BaseModel):
    message: str


class ApiSettings(BaseModel):
    api_url: str
    api_key: str
    model_name: str


class CustomDebaterRequest(BaseModel):
    name: str
    color: str = "#333333"
    avatar: str = "💬"
    stance: Literal["for", "against", "neutral"] = "neutral"
    personality: str
    enable_search: bool = True

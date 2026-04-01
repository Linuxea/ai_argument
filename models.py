from pydantic import BaseModel
from typing import Optional, Literal


class Debater(BaseModel):
    name: str
    color: str = "#333333"
    avatar: str = "💬"
    stance: Literal["for", "against", "neutral"] = "neutral"
    personality: str


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

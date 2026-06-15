"""Compatibility shim — real implementation now lives in :mod:`app.models`.

Kept so existing ``from models import ...`` imports keep working during the
staged refactor. Removed in stage 6.
"""
from app.models import (  # noqa: F401
    ArgumentSummary,
    CustomDebaterRequest,
    DebateConfig,
    Debater,
    RefineTopicRequest,
    UserMessage,
)

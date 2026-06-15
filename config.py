"""Compatibility shim — real implementation now lives in :mod:`app.config`.

Kept so existing ``from config import ...`` imports keep working during the
staged refactor. Removed in stage 6.
"""
from app.config import Settings, load_presets, settings  # noqa: F401

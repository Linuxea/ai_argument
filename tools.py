"""Compatibility shim — real implementation now lives in :mod:`app.tools`.

Kept so existing ``from tools import ...`` imports keep working during the
staged refactor. Removed in stage 6.
"""
from app.tools import web_search  # noqa: F401

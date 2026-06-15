"""Entry point for the AI Debate Chatroom.

The FastAPI application is assembled in :mod:`app` via :func:`app.create_app`;
this module just exposes it for ``uvicorn main:app``.
"""
from app import create_app

app = create_app()

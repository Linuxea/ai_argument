"""Debater routes: list presets/custom debaters and create custom ones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import load_presets
from app.deps import DebaterRepository, get_debater_repository
from app.models import CustomDebaterRequest, Debater

router = APIRouter(tags=["debaters"])


@router.get("/api/presets")
async def get_presets():
    """Get all preset debaters."""
    return [d.model_dump() for d in load_presets()]


@router.get("/api/debaters")
async def get_all_debaters(
    repository: DebaterRepository = Depends(get_debater_repository),
):
    """Get all available debaters (presets + custom)."""
    return [d.model_dump() for d in repository.list_all()]


@router.post("/api/debaters")
async def create_debater(
    request: CustomDebaterRequest,
    repository: DebaterRepository = Depends(get_debater_repository),
):
    """Create a custom debater."""
    debater = Debater(
        name=request.name,
        color=request.color,
        avatar=request.avatar,
        stance=request.stance,
        personality=request.personality,
        enable_search=request.enable_search,
    )
    if not await repository.add(debater):
        raise HTTPException(status_code=409, detail="Debater name already exists")
    return {"status": "created", "debater": debater.model_dump()}

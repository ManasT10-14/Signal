"""Webhooks API router — ASR webhooks removed (transcript-only mode)."""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.api_route("/{path:path}", methods=["GET", "POST"])
async def webhook_not_found(path: str):
    raise HTTPException(status_code=404, detail="Webhooks disabled in transcript-only mode")

"""
FastAPI dependencies — injected into route handlers.
"""
from __future__ import annotations

import uuid
from typing import Annotated, AsyncIterator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from signalapp.app.config import get_config
from signalapp.db.repository import (
    init_db,
    get_session,
    CallRepository,
    TranscriptRepository,
    AnalysisRunRepository,
    InsightRepository,
    BaseMetricRepository,
)

# HTTP Bearer token security
security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator:
    """Database session dependency."""
    async for session in get_session():
        yield session


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """
    Extract and validate the current user ID from the Authorization header.

    Phase 1: Simple API key auth. The API key is the user's ID.
    Phase 2: JWT-based auth with org_id context.
    """
    if not authorization:
        # Phase 1: No auth system — allow unauthenticated access with default user
        # Phase 2: Replace with JWT/OAuth validation
        return uuid.UUID("00000000-0000-0000-0000-000000000001")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # In Phase 2: decode JWT and extract user_id and org_id
    # For now: treat the bearer token as a user UUID
    try:
        user_id = uuid.UUID(authorization)
        return user_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )


# Type aliases for cleaner route signatures
DBSession = Annotated[AsyncIterator, Depends(get_db)]
CurrentUserID = Annotated[uuid.UUID, Depends(get_current_user_id)]


# Repository dependencies
def get_call_repo() -> CallRepository:
    return CallRepository()


def get_transcript_repo() -> TranscriptRepository:
    return TranscriptRepository()


def get_analysis_run_repo() -> AnalysisRunRepository:
    return AnalysisRunRepository()


def get_insight_repo() -> InsightRepository:
    return InsightRepository()


def get_base_metric_repo() -> BaseMetricRepository:
    return BaseMetricRepository()


CallRepo = Annotated[CallRepository, Depends(get_call_repo)]
TranscriptRepo = Annotated[TranscriptRepository, Depends(get_transcript_repo)]
AnalysisRunRepo = Annotated[AnalysisRunRepository, Depends(get_analysis_run_repo)]
InsightRepo = Annotated[InsightRepository, Depends(get_insight_repo)]
BaseMetricRepo = Annotated[BaseMetricRepository, Depends(get_base_metric_repo)]

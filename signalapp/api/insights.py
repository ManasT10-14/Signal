"""
Insights API router — /api/v1/insights
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from signalapp.app.dependencies import InsightRepo, CallRepo, CurrentUserID

router = APIRouter()


class InsightEvidence(BaseModel):
    segment_id: str
    timestamp: int
    speaker: str
    quote: str


class InsightResponse(BaseModel):
    id: str
    call_id: str
    framework_result_id: str
    priority_rank: int
    is_top_insight: bool
    framework_name: str
    severity: str
    confidence: float
    headline: str
    explanation: str
    evidence: list[InsightEvidence]
    coaching_recommendation: str
    created_at: str


class InsightFeedbackRequest(BaseModel):
    feedback: str | None = None  # "positive" | "negative" | null


class CallInsightsResponse(BaseModel):
    call_id: str
    run_id: str | None
    insights: list[InsightResponse]
    summary: dict | None


@router.get("/call/{call_id}", response_model=CallInsightsResponse)
async def get_call_insights(
    call_id: str,
    user_id: CurrentUserID,
    call_repo: CallRepo,
    insight_repo: InsightRepo,
) -> CallInsightsResponse:
    """Get all insights for a call."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid call_id format")

    call = await call_repo.get_by_id(call_uuid)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    # Get latest analysis run
    run_id = None
    if call.analysis_runs:
        latest_run = sorted(call.analysis_runs, key=lambda r: r.run_number, reverse=True)[-1]
        run_id = latest_run.id

    # Get insights
    insights = await insight_repo.get_for_call(call_uuid, run_id)

    # Build summary from latest run
    summary = None
    if call.analysis_runs:
        latest_run = sorted(call.analysis_runs, key=lambda r: r.run_number, reverse=True)[-1]
        if latest_run.framework_results:
            # Build a basic summary
            severity_counts = {"red": 0, "orange": 0, "yellow": 0, "green": 0}
            for fr in latest_run.framework_results:
                sev = fr.severity.lower()
                if sev in severity_counts:
                    severity_counts[sev] += 1
            summary = {
                "total_frameworks": len(latest_run.framework_results),
                "severity_breakdown": severity_counts,
                "status": latest_run.status,
            }

    return CallInsightsResponse(
        call_id=call_id,
        run_id=str(run_id) if run_id else None,
        insights=[
            InsightResponse(
                id=str(i.id),
                call_id=str(i.call_id),
                framework_result_id=str(i.framework_result_id),
                priority_rank=i.priority_rank,
                is_top_insight=i.is_top_insight,
                framework_name=i.framework_name,
                severity=i.severity,
                confidence=i.confidence,
                headline=i.headline,
                explanation=i.explanation,
                evidence=[InsightEvidence(**e) for e in (i.evidence or [])],
                coaching_recommendation=i.coaching_recommendation,
                created_at=i.created_at.isoformat(),
            )
            for i in insights
        ],
        summary=summary,
    )


@router.post("/{insight_id}/feedback")
async def submit_insight_feedback(
    insight_id: str,
    feedback_req: InsightFeedbackRequest,
    user_id: CurrentUserID,
    insight_repo: InsightRepo,
) -> dict:
    """Submit user feedback on an insight."""
    from datetime import datetime

    try:
        insight_uuid = uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight_id format")

    # Validate feedback value
    valid_feedback = feedback_req.feedback
    if valid_feedback is not None and valid_feedback not in ("positive", "negative"):
        raise HTTPException(status_code=422, detail="feedback must be 'positive', 'negative', or null")

    # Update insight with feedback
    insight = await insight_repo.update_feedback(
        insight_id=insight_uuid,
        feedback=valid_feedback,
        feedback_at=datetime.utcnow(),
    )

    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")

    return {
        "status": "ok",
        "insight_id": insight_id,
        "feedback": insight.feedback,
        "feedback_at": insight.feedback_at.isoformat() if insight.feedback_at else None,
    }

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
    segment_id: str = ""
    timestamp: int = 0
    speaker: str = ""
    quote: str = ""
    quote_match_score: float = 0.0
    quote_verified: bool = False


class InsightResponse(BaseModel):
    id: str
    call_id: str
    framework_result_id: str
    prompt_group: str = ""
    priority_rank: int
    is_top_insight: bool
    is_aim_null_finding: bool = False
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

    # Build summary — prefer stored rich summary from analysis run, fallback to insights-derived
    summary = None

    # Try to get stored summary from latest analysis run
    if call.analysis_runs:
        latest_run = sorted(call.analysis_runs, key=lambda r: r.run_number, reverse=True)[-1]
        if latest_run.framework_results:
            severity_counts = {"red": 0, "orange": 0, "yellow": 0, "green": 0}
            for fr in latest_run.framework_results:
                sev = (fr.severity or "green").lower()
                if sev in severity_counts:
                    severity_counts[sev] += 1

            if latest_run.summary and isinstance(latest_run.summary, dict):
                summary = dict(latest_run.summary)
                summary["severity_breakdown"] = severity_counts
                summary["total_frameworks"] = len(latest_run.framework_results)

    # Fallback: build summary from insights if no stored summary
    if summary is None and insights:
        summary = _build_fallback_summary(insights)

    return CallInsightsResponse(
        call_id=call_id,
        run_id=str(run_id) if run_id else None,
        insights=[
            InsightResponse(
                id=str(i.id),
                call_id=str(i.call_id),
                framework_result_id=str(i.framework_result_id),
                prompt_group=_get_prompt_group(i.framework_name),
                priority_rank=i.priority_rank,
                is_top_insight=i.is_top_insight,
                is_aim_null_finding=i.is_aim_null_finding,
                framework_name=i.framework_name,
                severity=i.severity,
                confidence=i.confidence,
                headline=i.headline,
                explanation=i.explanation,
                evidence=[InsightEvidence(**{k: v for k, v in e.items() if k in InsightEvidence.model_fields}) for e in (i.evidence or [])],
                coaching_recommendation=i.coaching_recommendation,
                created_at=i.created_at.isoformat(),
            )
            for i in insights
        ],
        summary=summary,
    )


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    user_id: CurrentUserID,
    insight_repo: InsightRepo,
    call_repo: CallRepo,
) -> dict:
    """
    Single-query dashboard summary: top severity calls, avg confidence, top coaching theme.
    Replaces the N+1 pattern of fetching insights for every call individually.
    """
    from signalapp.db.repository import get_session
    from signalapp.db.models import Insight, Call
    from sqlalchemy import select, func, desc
    from datetime import datetime, timedelta

    try:
        async for session in get_session():
            # Get all insights with their call info in one query
            result = await session.execute(
                select(
                    Insight.call_id,
                    Insight.severity,
                    Insight.confidence,
                    Insight.headline,
                    Insight.framework_name,
                    Insight.priority_rank,
                    Insight.is_top_insight,
                    Call.rep_name,
                    Call.call_type,
                    Call.deal_name,
                    Call.created_at,
                )
                .join(Call, Insight.call_id == Call.id)
                .where(Call.processing_status == "ready")
            )
            rows = result.all()

        # Sort in Python: RED first, then ORANGE, then by confidence desc
        sev_rank = {"red": 0, "orange": 1, "yellow": 2, "green": 3}
        rows = sorted(rows, key=lambda r: (sev_rank.get(r.severity, 9), -(r.confidence or 0)))

        if not rows:
            return {
                "attention_calls": [],
                "avg_confidence": 0,
                "top_coaching_theme": "",
                "theme_counts": {},
            }

        # Build attention calls (top 5 red/orange)
        attention_calls = []
        seen_calls = set()
        for row in rows:
            if row.severity in ("red", "orange") and str(row.call_id) not in seen_calls and len(attention_calls) < 5:
                seen_calls.add(str(row.call_id))
                attention_calls.append({
                    "call_id": str(row.call_id),
                    "severity": row.severity,
                    "confidence": row.confidence,
                    "headline": row.headline,
                    "framework_name": row.framework_name,
                    "rep_name": row.rep_name,
                    "call_type": row.call_type,
                    "deal_name": row.deal_name,
                })

        # Avg confidence
        confidences = [r.confidence for r in rows if r.confidence]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Top coaching theme (most common framework in red/orange)
        theme_counts = {}
        for r in rows:
            if r.severity in ("red", "orange") and r.framework_name:
                theme_counts[r.framework_name] = theme_counts.get(r.framework_name, 0) + 1

        top_theme = max(theme_counts, key=theme_counts.get) if theme_counts else ""

        return {
            "attention_calls": attention_calls,
            "avg_confidence": round(avg_confidence, 3),
            "top_coaching_theme": top_theme,
            "theme_counts": theme_counts,
        }

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Dashboard summary error: {e}")
        return {
            "attention_calls": [],
            "avg_confidence": 0,
            "top_coaching_theme": "",
            "theme_counts": {},
        }


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


# Framework name → prompt group mapping
_FW_GROUP_MAP = {
    "BATNA Detection": "A", "Money Left on Table": "A", "First Number Tracker": "A",
    "Deal Health at Close": "A", "Deal Timing Intelligence": "A",
    "Unanswered Questions": "B", "Commitment Quality": "B",
    "Commitment Thermometer": "B", "Pushback Classification": "B",
    "Question Quality": "C", "Frame Match Score": "C", "Close Attempt Analysis": "C",
    "Methodology Compliance": "C", "Call Structure Analysis": "C", "Objection Response Score": "C",
    "NEPQ Methodology Analysis": "F",
    "Emotional Turning Points": "E", "Emotional Trigger Analysis": "E",
}


def _get_prompt_group(framework_name: str) -> str:
    return _FW_GROUP_MAP.get(framework_name, "")


def _build_fallback_summary(insights) -> dict:
    """Build a useful summary dict from insight objects when no stored summary exists."""
    severity_counts = {"red": 0, "orange": 0, "yellow": 0, "green": 0}
    for ins in insights:
        sev = (ins.severity or "green").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    red = severity_counts.get("red", 0)
    orange = severity_counts.get("orange", 0)

    if red >= 2:
        headline = "High-risk call with multiple critical issues"
        assessment = "High risk — multiple critical issues suggest deal may stall without intervention"
    elif red == 1:
        headline = "Call with one critical issue requiring attention"
        assessment = "Moderate risk — one critical issue needs immediate attention"
    elif orange >= 2:
        headline = "Moderate-risk call with engagement gaps"
        assessment = "Cautious — several areas need coaching before next interaction"
    elif orange == 1:
        headline = "Call with some areas for improvement"
        assessment = "Progressing — minor coaching opportunities identified"
    else:
        headline = "Generally positive call dynamics"
        assessment = "Healthy — no significant behavioral concerns detected"

    sorted_ins = sorted(insights, key=lambda x: x.priority_rank)
    top_headlines = [ins.headline for ins in sorted_ins[:3] if ins.headline]
    recap = f"{headline}. " + " ".join(top_headlines[:2]) if top_headlines else headline

    coaching = ""
    if sorted_ins and sorted_ins[0].coaching_recommendation:
        coaching = sorted_ins[0].coaching_recommendation[:300]

    return {
        "headline": headline,
        "recap": recap.strip(),
        "key_decisions": [],
        "action_items_rep": [],
        "action_items_buyer": [],
        "open_questions": [],
        "deal_assessment": assessment,
        "coaching_focus": coaching,
        "key_themes": top_headlines,
        "severity_breakdown": severity_counts,
        "total_frameworks": len(insights),
    }

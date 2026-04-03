"""
Insight domain models — Insight entity and prioritization logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class InsightFeedback(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NONE = None


@dataclass
class Insight:
    """A surfaced insight ready for user display."""

    insight_id: str
    call_id: str
    framework_result_id: str
    priority_rank: int
    is_top_insight: bool = False
    feedback: InsightFeedback = InsightFeedback.NONE
    feedback_at: Optional[str] = None

    # Core content
    framework_name: str
    severity: str  # red, orange, yellow, green
    confidence: float
    headline: str
    explanation: str
    evidence: list[dict]  # List of {segment_id, timestamp, speaker, quote}
    coaching_recommendation: str

    # Metadata
    created_at: str


# Severity rank for sorting (lower = more important)
SEVERITY_RANK = {"red": 0, "orange": 1, "yellow": 2, "green": 3}


def prioritize_insights(
    insights: list[Insight], top_n: int = 5
) -> list[Insight]:
    """
    Sort and select top insights.
    Priority: severity → confidence → actionability.
    """
    # Sort: severity rank first, then confidence descending
    sorted_insights = sorted(
        insights,
        key=lambda i: (SEVERITY_RANK.get(i.severity, 99), -i.confidence),
    )

    # Mark top insights and assign priority ranks
    for idx, insight in enumerate(sorted_insights[:top_n]):
        insight.priority_rank = idx + 1
        insight.is_top_insight = True

    # Assign ranks to rest
    for idx, insight in enumerate(sorted_insights[top_n:]):
        insight.priority_rank = top_n + idx + 1
        insight.is_top_insight = False

    return sorted_insights

"""
Group A — Deal Health at Close framework prompt — v1.

Evaluates deal health indicators at close phase.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class DealHealthOutput(BaseModel):
    health_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    indicators: list[dict] = Field(default_factory=list)
    # {indicator_type, present, evidence_segment_id, quote}

    red_flags: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, flag_type}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to evaluate deal health at close.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. Health indicators: clear authority, budget confirmed, timeline agreed, scope defined
3. Red flags: unresolved objections, authority gaps, budget concerns, competing priorities
4. Absence of positive indicators is itself a signal (AIM pattern)

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Evaluate presence of 4 health indicators.
Step 2: Identify red flags.
Step 3: Calculate overall health score.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

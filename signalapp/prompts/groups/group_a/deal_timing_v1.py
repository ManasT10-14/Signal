"""
Group A — Deal Timing Intelligence framework prompt — v1.

Detects timing signals and urgency indicators.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class TimingSignal(BaseModel):
    segment_id: str
    signal_type: str  # "urgency" | "delay" | "stall" | "timeline"
    signal_text: str
    speaker: str
    is_buyer_initiated: bool


class DealTimingOutput(BaseModel):
    overall_urgency_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    timing_signals: list[TimingSignal] = Field(default_factory=list)

    red_flags: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, flag_type}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to identify deal timing signals.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. Urgency signals: budget cycles, Q-end, competing deals, leadership changes
3. Delay signals: "need to think", "discuss with team", "next quarter"
4. Stall signals: repeated topic changes, no forward movement, vague next steps
5. Do NOT fabricate — output empty list if no signals found

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify all timing-related language.
Step 2: Classify each as urgency/delay/stall/timeline.
Step 3: Calculate urgency score.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

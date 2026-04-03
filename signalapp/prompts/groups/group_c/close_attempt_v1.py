"""
Group C — Close Attempt Analysis framework prompt — v1.

Analyzes close attempts and commitment extraction.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CloseAttempt(BaseModel):
    segment_id: str
    close_type: str  # "direct" | "试探" | "assumptive" | "urgency"
    close_text: str
    buyer_response: str  # "accepted" | "deflected" | "ignored" | "counter"
    speaker: str


class CloseAttemptOutput(BaseModel):
    total_close_attempts: int
    successful_closes: int
    failed_closes: int

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    close_attempts: list[CloseAttempt] = Field(default_factory=list)

    missed_opportunities: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, reason}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to analyze close attempts.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. Close types: direct (ask for the sale),试探 (test the water), assumptive (act like done), urgency (time pressure)
3. Buyer response: accepted, deflected, ignored, counter (conditions)
4. Missed opportunities: natural closing moments where rep did not attempt close

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Find all close attempts.
Step 2: Classify buyer response.
Step 3: Identify missed opportunities.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.

---
AIM PATTERN — MANDATORY ON demo/pricing/negotiation/close CALLS:
If zero close attempts found, do NOT return empty/null. Return:
- total_close_attempts: 0
- successful_closes: 0
- failed_closes: 0
- is_aim_null_finding: true
- missed_opportunities: identify 2-3 natural closing moments where rep could have attempted to close but did not. For each, provide segment_id, timestamp, speaker, quote, and reason why it was a close opportunity.
- severity: "orange"
- headline: "Zero close attempts — missed coaching opportunity"
- explanation: "No close attempts were detected on a [call_type] call. Natural closing moments were identified where the rep could have moved toward commitment but passed on the opportunity."
- coaching_recommendation: "Practice the trial close: 'Based on what we've discussed, does it make sense to schedule next steps?' Identify the natural close moments in the transcript and rehearse how to capitalize on them."
"""

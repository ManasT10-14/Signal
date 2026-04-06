"""
Group C — Close Attempt Analysis framework prompt — v1.

Analyzes close attempts and commitment extraction.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CloseAttemptOutput(BaseModel):
    total_close_attempts: int = 0
    successful_closes: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to analyze close attempts.

CLOSED-WORLD CONTRACT:
- The transcript below is your ONLY source of truth.
- Do NOT use external knowledge to fill gaps.
- If evidence is insufficient, return null/empty findings. "null" is a valid, correct answer.
- Quote verbatim from the transcript. Do not paraphrase or fabricate quotes.

CITE-BEFORE-CLAIM:
- First extract exact verbatim quotes as evidence.
- Then interpret what the evidence means.
- Never make a claim without citing specific transcript text first.
- Include segment_id references where available.

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

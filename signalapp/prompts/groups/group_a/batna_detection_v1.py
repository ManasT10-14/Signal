"""
Group A — BATNA Detection framework prompt — v1.

Detects buyer's Best Alternative to Negotiated Agreement signals.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class BatnaDetectionOutput(BaseModel):
    buyer_leverage_score: float = 0.0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to detect BATNA signals.

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
2. BATNA = buyer's alternatives to this deal (competitor, status quo, internal option)
3. Direct mention: "we're also talking to X", "X offered us Y"
4. Implicit: "our current solution works fine", "we don't urgently need this"
5. AIM pattern: absence of alternatives is itself a weak signal (absence of strength ≠ weakness)

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Find all alternative mentions (competitors, current solution, internal options).
Step 2: Classify each as direct/implicit.
Step 3: Calculate buyer leverage score.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.

---
AIM PATTERN — MANDATORY ON pricing/negotiation/close CALLS:
If no alternative mentions are found, do NOT return empty/null. Return:
- has_mentioned_alternative: false
- alternative_count: 0
- buyer_leverage_score: 0.85 (weak BATNA = rep has leverage)
- is_aim_null_finding: true
- aim_output: "No alternatives mentioned. Weak BATNA — buyer has limited walkaway options."
- severity: "green"
- headline: "Weak buyer BATNA — leverage confirmed"
- explanation: "Buyer did not reference any alternatives during this call. This suggests they have limited walkaway options and the rep has pricing leverage."
- coaching_recommendation: "Hold the pricing position. Without competitive alternatives, the buyer has less bargaining power."
"""

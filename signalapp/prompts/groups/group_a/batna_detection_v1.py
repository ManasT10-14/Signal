"""
Group A — BATNA Detection framework prompt — v1.

Detects buyer's Best Alternative to Negotiated Agreement signals.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field


class AltMentionInstance(BaseModel):
    segment_id: str
    alternative_name: str  # "CompetitorX", "current solution", "internal build"
    mention_type: str  # "direct_comparison" | "implicit" | "internal_option"
    speaker: str
    quote: str


class BatnaDetectionOutput(BaseModel):
    has_mentioned_alternative: bool = False
    alternative_count: int = 0
    buyer_leverage_score: float = Field(ge=0.0, le=1.0)

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    alternative_mentions: list[AltMentionInstance] = Field(default_factory=list)

    # AIM output when no alternatives found
    is_aim_null_finding: bool = False
    aim_output: str = ""

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to detect BATNA signals.

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

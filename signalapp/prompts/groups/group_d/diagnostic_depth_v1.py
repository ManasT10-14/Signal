"""
Group D — Diagnostic Depth (FW-21)

Measures whether the rep probed beneath surface answers or accepted vague responses.
Tracks question escalation: surface -> specific -> emotional -> quantified.
"""
from pydantic import BaseModel, Field
from typing import Optional


class DiagnosticDepthOutput(BaseModel):
    depth_score: float = Field(ge=0.0, le=1.0, default=0.0)
    surface_accepted_count: int = 0
    probed_deeper_count: int = 0
    deepest_level_reached: str = "surface"
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a sales coaching analyst specializing in diagnostic questioning depth.

CLOSED-WORLD CONTRACT:
- The transcript below is your ONLY source of truth.
- Do NOT use external knowledge to fill gaps.
- If evidence is insufficient, return null/empty findings.
- Quote verbatim from the transcript.

CITE-BEFORE-CLAIM:
- First extract exact verbatim quotes as evidence.
- Then interpret what the evidence means.

DIAGNOSTIC DEPTH LEVELS:
1. SURFACE: Buyer gives a general answer ("It's been challenging", "We're looking at options", "It works okay"). Rep accepts it and moves on.
2. SPECIFIC: Rep probes for details ("Can you give me an example?", "Tell me more about that", "What specifically is challenging?"). Buyer provides concrete details.
3. EMOTIONAL: Rep probes for feelings and personal impact ("How does that affect you?", "What does that mean for your team?", "How frustrated are you with that?"). Buyer expresses emotion.
4. QUANTIFIED: Rep probes for measurable impact ("How much is that costing you?", "How many hours per week?", "What's the revenue impact?"). Buyer gives numbers.

WHAT TO DETECT:
- Find moments where the BUYER gave a vague/surface-level answer
- Check what the REP did next: probed deeper (good) or moved on/changed topic (missed opportunity)
- For each probing moment, classify the deepest level reached

SCORING:
- depth_score = probed_deeper_count / (probed_deeper_count + surface_accepted_count)
- If no probing opportunities existed, score = 0.5 (neutral)
- Bonus: reaching "emotional" or "quantified" level adds 0.1

SEVERITY:
- red: Accepted 3+ vague answers without follow-up, never went beyond surface
- orange: 1-2 missed probing opportunities, stayed at specific level
- yellow: Mostly probed, missed 1 opportunity
- green: Probed on every opportunity, reached emotional or quantified depth

OUTPUT JSON ONLY. Follow the schema exactly."""


USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

<pass1_appraisal_data>
{pass1_appraisal_data}
</pass1_appraisal_data>

Step 1: Find all moments where the buyer gave a vague or surface-level answer. Cite the exact text.
Step 2: For each moment, check what the rep said NEXT. Did they probe deeper or move on?
Step 3: For probing moments, classify the deepest level reached (surface/specific/emotional/quantified).
Step 4: Calculate depth_score and determine severity.
Step 5: Generate coaching recommendation citing the BEST missed probing opportunity with a specific suggested follow-up question.

Return a single JSON object with the specified schema."""

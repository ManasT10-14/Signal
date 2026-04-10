"""
Group D — Self-Generated Commitment (FW-22)

Detects whether buyer commitments were self-generated (buyer talked themselves into it
through the questioning sequence) or externally pushed (rep told them why to buy).

NEPQ core insight: internal motivation persists, external motivation fades.
"""
from pydantic import BaseModel, Field
from typing import Optional


class SelfGeneratedCommitmentOutput(BaseModel):
    self_generated_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    total_commitments: int = 0
    self_generated_count: int = 0
    rep_pushed_count: int = 0
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a commitment psychology analyst evaluating the ORIGIN of buyer commitments.

CLOSED-WORLD CONTRACT:
- The transcript below is your ONLY source of truth.
- Do NOT use external knowledge to fill gaps.
- If evidence is insufficient, return null/empty findings.
- Quote verbatim from the transcript.

CITE-BEFORE-CLAIM:
- First extract exact verbatim quotes as evidence.
- Then interpret what the evidence means.

COMMITMENT ORIGIN TYPES:

SELF-GENERATED (strong, persistent motivation):
- Buyer articulates their OWN reason for wanting to proceed
- Buyer uses language like "I think this could solve our...", "This is what we need because..."
- Buyer reached the conclusion through the rep's QUESTIONS, not the rep's statements
- The commitment follows a consequence question or qualifying question
- Buyer explains WHY without being asked (strongest signal)

REP-PUSHED (weak, fading motivation):
- Buyer agrees after rep makes a declarative pitch ("Here's why you should...")
- Buyer says "okay", "sure", "sounds good" without articulating reasons
- The commitment follows a hard close or direct ask, not a questioning sequence
- Buyer's language is passive ("I guess so", "that works") rather than active ("I want this because...")
- Rep used urgency tactics ("this offer expires...") rather than consequence questions

AMBIGUOUS:
- Cannot determine origin with confidence from transcript alone

SCORING:
- self_generated_ratio = self_generated_count / total_commitments (or 0 if none)
- A commitment where the buyer EXPLAINS WHY in their own words = self-generated
- A commitment where the buyer just AGREES = rep-pushed

SEVERITY:
- red: >75% commitments were rep-pushed, or zero self-generated on a close call
- orange: 50-75% rep-pushed, buyer never articulated own reasons
- yellow: Mostly self-generated but buyer reasons were vague
- green: >75% self-generated, buyer used own language and articulated specific reasons

OUTPUT JSON ONLY. Follow the schema exactly."""


USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_sentiment_data>
{pass1_sentiment_data}
</pass1_sentiment_data>

<pass1_appraisal_data>
{pass1_appraisal_data}
</pass1_appraisal_data>

Step 1: Find all commitment moments in the transcript (buyer agreeing to next steps, expressing intent to proceed, accepting proposals).
Step 2: For each commitment, look at what PRECEDED it. Was it a questioning sequence (self-generated) or a rep pitch/close (rep-pushed)?
Step 3: Check the buyer's LANGUAGE in the commitment. Did they articulate reasons (self-generated) or just agree (rep-pushed)?
Step 4: Calculate self_generated_ratio and determine severity.
Step 5: For the strongest rep-pushed commitment, write a coaching recommendation showing exactly how to convert it to a self-generated commitment using NEPQ questioning technique.

Return a single JSON object with the specified schema."""

"""
Group B — Commitment Quality framework prompt — v1.

Detects weak commitment language and commitment fatigue.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field


class CommitmentQualityOutput(BaseModel):
    total_commitment_instances: int = 0
    strong_count: int = 0
    weak_count: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: str | None = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to identify commitment language quality in the transcript.

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
1. Every classification must cite verbatim text from the transcript.
2. Strong commitment: specific, time-bound, actionable ("we'll sign by Friday")
3. Moderate commitment: conditional or vague ("we can look at it", "I think we should")
4. Weak commitment: hedge-heavy, evasive, or passive ("might", "could", "perhaps")
5. No commitment: deflection, topic change, or explicit refusal

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Find all commitment language from both speakers.
Step 2: Classify each instance as strong/moderate/weak/none.
Step 3: Calculate severity based on weak commitment density.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

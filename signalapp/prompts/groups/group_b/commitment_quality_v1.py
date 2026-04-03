"""
Group B — Commitment Quality framework prompt — v1.

Detects weak commitment language and commitment fatigue.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CommitmentInstance(BaseModel):
    segment_id: str
    commitment_text: str
    strength: str  # "strong" | "moderate" | "weak" | "none"
    speaker: str
    timestamp_ms: int


class CommitmentQualityOutput(BaseModel):
    total_commitment_instances: int
    strong_count: int
    moderate_count: int
    weak_count: int

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    commitment_instances: list[CommitmentInstance] = Field(default_factory=list)

    # Evidence — verbatim segment references
    weak_segments: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to identify commitment language quality in the transcript.

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

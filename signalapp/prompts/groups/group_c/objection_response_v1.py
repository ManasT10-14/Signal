"""
Group C — Objection Response Score framework prompt — v1.

Scores the quality of objection handling.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field


class ObjectionResponse(BaseModel):
    segment_id: str
    objection_text: str
    response_text: str
    response_quality: str  # "excellent" | "good" | "poor" | "none"
    technique_used: str  # "feel_felt_found" | "reframe" | "answer" | "ignore" | "none"
    speaker: str


class ObjectionResponseOutput(BaseModel):
    total_objections: int
    excellent_count: int
    good_count: int
    poor_count: int
    unresolved_count: int

    response_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    objection_responses: list[ObjectionResponse] = Field(default_factory=list)

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to score objection responses.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. Excellent: directly addresses, reframe, feel-felt-found, or valid alternative
3. Good: acknowledges but doesn't fully address
4. Poor: dismisses, argues, or sidesteps without resolution
5. None: no response attempted when buyer raised concern

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify all buyer objections.
Step 2: Find rep's response to each.
Step 3: Score response quality.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

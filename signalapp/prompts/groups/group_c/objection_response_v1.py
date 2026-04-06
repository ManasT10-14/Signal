"""
Group C — Objection Response Score framework prompt — v1.

Scores the quality of objection handling.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class ObjectionResponseOutput(BaseModel):
    response_score: float = 0.0
    total_objections: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to score objection responses.

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

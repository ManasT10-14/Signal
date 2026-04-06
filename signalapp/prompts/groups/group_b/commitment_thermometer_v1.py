"""
Group B — Commitment Thermometer framework prompt — v1.

Tracks buyer commitment temperature throughout the call.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field


class CommitmentThermometerOutput(BaseModel):
    starting_temperature: float = 0.0
    ending_temperature: float = 0.0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: str | None = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to track commitment temperature.

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
2. Temperature indicators: specific commitment (high), general interest (medium), deflection (low)
3. Track trajectory over the call: heating, cooling, stable, or volatile
4. Cold spell = sudden drop in temperature mid-call
5. Rate each segment or significant moment

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Rate commitment temperature at key moments.
Step 2: Track trajectory across the call.
Step 3: Identify cold spells.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

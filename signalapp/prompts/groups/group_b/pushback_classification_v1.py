"""
Group B — Pushback Classification framework prompt — v1.

Classifies buyer pushback types and severity.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field


class PushbackClassificationOutput(BaseModel):
    total_pushback_events: int = 0
    unresolved_count: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: str | None = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to classify pushback.

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
2. Pushback types: price, timeline, feature gap, authority, competing priority
3. Severity: low (minor concern), medium (blocking but addressable), high (deal-threatening)
4. Resolved = rep successfully addressed; Unresolved = still blocking
5. Do NOT fabricate pushback — output empty list if none found

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify all pushback events.
Step 2: Classify type and severity.
Step 3: Determine if resolved.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

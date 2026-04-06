"""
Group A — Money Left on Table framework prompt — v1.

Detects concession patterns and pricing flexibility signals.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class MoneyLeftOnTableOutput(BaseModel):
    total_concessions: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to identify money left on the table signals.

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
2. A concession is any flexibility offered: price reduction, extended timeline, added scope
3. Unmet buyer requests are things buyer asked for but rep did not concede to
4. Track who initiated each concession (rep vs buyer)
5. Do NOT fabricate concessions — output empty list if none found

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify all concessions (price, terms, timeline, scope).
Step 2: Note who initiated each concession.
Step 3: Identify buyer requests that were not conceded.
Step 4: Calculate severity based on rep-initiated vs buyer-asked ratio.
Step 5: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

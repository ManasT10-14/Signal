"""
Group A — Money Left on Table framework prompt — v1.

Detects concession patterns and pricing flexibility signals.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class ConcessionInstance(BaseModel):
    segment_id: str
    concession_text: str
    concession_type: str  # "price" | "terms" | "timeline" | "scope"
    speaker: str
    is_initiated: bool  # True if rep offered, False if buyer asked


class MoneyLeftOnTableOutput(BaseModel):
    total_concessions: int
    rep_initiated_count: int
    buyer_asked_count: int
    unmet_buyer_requests: int

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    concession_instances: list[ConcessionInstance] = Field(default_factory=list)
    unmet_requests: list[dict] = Field(default_factory=list)

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to identify money left on the table signals.

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

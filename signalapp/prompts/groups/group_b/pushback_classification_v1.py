"""
Group B — Pushback Classification framework prompt — v1.

Classifies buyer pushback types and severity.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field


class PushbackInstance(BaseModel):
    segment_id: str
    pushback_type: str  # "price" | "timeline" | "feature" | "authority" | "competing_priority" | "other"
    severity: str  # "low" | "medium" | "high"
    buyer_statement: str
    rep_response: str | None = None
    is_resolved: bool = False


class PushbackClassificationOutput(BaseModel):
    total_pushback_events: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    pushback_instances: list[PushbackInstance] = Field(default_factory=list)

    unresolved_issues: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, pushback_type}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to classify pushback.

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

"""
Group C — Frame Match Score framework prompt — v1.

Measures alignment between rep framing and buyer priorities.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field


class FrameMatchOutput(BaseModel):
    alignment_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    buyer_priorities: list[str] = Field(default_factory=list)
    rep_frame_topics: list[str] = Field(default_factory=list)
    alignment_moments: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, alignment_type}

    misalignment_moments: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, misalignment_type}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to measure frame match.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. Frame = how a topic is presented (features, benefits, cost, risk, etc.)
3. Match = rep's frame aligns with what buyer cares about
4. Misalignment = rep talks past buyer priorities

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify buyer-stated priorities.
Step 2: Identify rep's framing topics.
Step 3: Compare for alignment/misalignment.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

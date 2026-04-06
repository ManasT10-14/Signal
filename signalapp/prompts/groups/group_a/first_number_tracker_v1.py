"""
Group A — First Number Tracker framework prompt — v1.

Tracks the first number mentioned and its strategic implications.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class FirstNumberTrackerOutput(BaseModel):
    first_price_speaker: Optional[str] = None
    anchor_effect_detected: bool = False
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to track first numbers.

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
2. First number in a category (price, discount, timeline) creates an anchor
3. Track who mentioned first: buyer anchor vs rep anchor has different implications
4. Numbers include: dollar amounts, percentages, quantities, time periods

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

Step 1: Find all numeric mentions.
Step 2: Classify by type (price, discount, timeline, quantity).
Step 3: Identify first mention in each category and who said it.
Step 4: Detect anchor effects.
Step 5: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

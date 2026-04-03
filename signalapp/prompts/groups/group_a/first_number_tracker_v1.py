"""
Group A — First Number Tracker framework prompt — v1.

Tracks the first number mentioned and its strategic implications.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class NumberMention(BaseModel):
    segment_id: str
    number_value: str  # e.g., "$50K", "50%", "3 months"
    number_type: str  # "price" | "discount" | "timeline" | "quantity" | "other"
    speaker: str
    is_anchor: bool  # True if first number in relevant category
    quote: str


class FirstNumberTrackerOutput(BaseModel):
    first_price_speaker: Optional[str] = None
    first_price_value: Optional[str] = None
    first_discount_speaker: Optional[str] = None
    first_discount_value: Optional[str] = None

    anchor_effect_detected: bool = False
    number_count: int = 0

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    number_mentions: list[NumberMention] = Field(default_factory=list)

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to track first numbers.

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

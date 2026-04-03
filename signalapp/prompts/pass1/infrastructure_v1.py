"""
Pass 1: Infrastructure extraction prompt — v1.

Extracts three shared infrastructure signals from the full transcript:
1. Hedge density + type classification per segment
2. Sentiment trajectory per segment
3. Evaluative language (appraisal) per segment

This runs ONCE per call. Output is consumed by all Pass 2 frameworks.
Single LLM call, structured output via Pydantic schema.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ─── Output Schemas ────────────────────────────────────────────────────────────

class HedgeInstance(BaseModel):
    segment_id: str
    hedge_text: str
    hedge_type: str  # "epistemic" | "politeness" | "strategic"
    confidence: float = Field(ge=0.0, le=1.0)


class SentimentPoint(BaseModel):
    segment_id: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    notable_shift: bool  # True if delta from previous > 0.3


class AppraisalInstance(BaseModel):
    segment_id: str
    appraisal_type: str  # "affect" | "judgment" | "appreciation"
    target: str  # What is being evaluated: "product", "team", "timeline", "price"
    polarity: str  # "strongly_positive" | "positive" | "neutral" | "negative" | "strongly_negative"
    text_excerpt: str


class Pass1Output(BaseModel):
    # Per-segment hedge instances
    hedges: list[HedgeInstance] = Field(default_factory=list)
    # Overall hedge density per speaker
    hedge_density_buyer: float = Field(ge=0.0, le=1.0, description="Buyer hedge density 0-1")
    hedge_density_rep: float = Field(ge=0.0, le=1.0, description="Rep hedge density 0-1")

    # Per-segment sentiment
    sentiment_trajectory: list[SentimentPoint] = Field(default_factory=list)

    # Per-segment evaluative language
    evaluative_language: list[AppraisalInstance] = Field(default_factory=list)

    # Cross-cutting signals
    contains_comparison_language: bool = Field(
        default=False,
        description="Any speaker compared to a competitor or alternative"
    )
    contains_dollar_amount: bool = Field(
        default=False,
        description="Any specific dollar amount mentioned"
    )
    first_number_speaker: Optional[str] = Field(
        default=None,
        description="Speaker who stated the first specific number"
    )
    transcript_duration_minutes: float = Field(default=0.0)


# ─── Prompt Template ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are analyzing a sales call transcript. Your task is to extract three infrastructure signals that other analysis frameworks will consume.

BEHAVIORAL CONSTITUTION FOR THIS ANALYSIS:

1. EVIDENCE PRINCIPLE: Every classification must be anchored in verbatim text from the transcript.
2. NULL PRINCIPLE: If a signal is absent, output it as absent (empty list or false). Do NOT fabricate.
3. PRECISION PRINCIPLE: Hedge types, sentiment scores, and appraisal classifications must be specific and accurate.
4. CLOSED WORLD: The transcript is your only source. Do not infer speaker intent beyond what the text shows.

OUTPUT JSON ONLY. No explanation, no preamble."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

Extract the three infrastructure signals from this transcript.

Return a single JSON object with:
- hedges: list of hedge instances (epistemic/politeness/strategic)
- hedge_density_buyer: overall buyer hedge density 0-1
- hedge_density_rep: overall rep hedge density 0-1
- sentiment_trajectory: sentiment score per segment (-1 to +1) with shift detection
- evaluative_language: appraisal instances (affect/judgment/appreciation) with polarity and target
- contains_comparison_language: bool
- contains_dollar_amount: bool
- first_number_speaker: name of speaker who stated first number, or null
- transcript_duration_minutes: estimated duration in minutes

Hedge types:
- epistemic: "I think", "maybe", "probably", "I believe"
- politeness: "perhaps you could", "it might be worth", "I wonder if"
- strategic: "we might consider", "there could be flexibility", "it's possible"

Sentiment scale: -1 (very negative) to +1 (very positive).
Notable shift = delta from previous segment > 0.3.

Appraisal types:
- affect: "I feel frustrated" — emotional reaction
- judgment: "your team can't deliver" — evaluation of people/capability
- appreciation: "the product is elegant" — evaluation of things/processes
"""


def build_pass1_prompt(transcript_text: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    return SYSTEM_PROMPT, USER_PROMPT.format(transcript_text=transcript_text)

"""
Group E — Emotional Turning Points & Emotion Trigger framework prompt — v1.

Detects emotional high points and triggering language.
Part of the Emotional Resonance group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class EmotionTriggerOutput(BaseModel):
    positive_shift_count: int = 0
    negative_shift_count: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to detect emotional dynamics.

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
2. Emotional turning point: moment where sentiment shifts significantly (>0.3 delta)
3. Emotion trigger: language that caused or predicts an emotional response
4. Detect: frustration, excitement, concern, relief, surprise, disappointment
5. Combine both FW-08 (Turning Points) and FW-09 (Triggers) in this single output

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_sentiment_data>
{pass1_sentiment_data}
</pass1_sentiment_data>

<pass1_appraisal_data>
{pass1_appraisal_data}
</pass1_appraisal_data>

Step 1: Find emotional turning points from sentiment data.
Step 2: Identify emotion triggers from appraisal data.
Step 3: Classify each by type and intensity.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

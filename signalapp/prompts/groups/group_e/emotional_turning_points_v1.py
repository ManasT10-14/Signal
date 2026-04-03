"""
Group E — Emotional Turning Points & Emotion Trigger framework prompt — v1.

Detects emotional high points and triggering language.
Part of the Emotional Resonance group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class EmotionalTurningPoint(BaseModel):
    segment_id: str
    turning_point_type: str  # "positive_shift" | "negative_shift" | "neutral_peak"
    emotion_detected: str  # "frustration" | "excitement" | "concern" | "relief" | etc.
    intensity: float = Field(ge=0.0, le=1.0)
    text_excerpt: str
    speaker: str


class EmotionTriggerOutput(BaseModel):
    # Emotional Turning Points
    turning_points: list[EmotionalTurningPoint] = Field(default_factory=list)
    positive_shift_count: int = 0
    negative_shift_count: int = 0

    # Emotion Triggers (combined with 8)
    trigger_segments: list[dict] = Field(default_factory=list)
    # {segment_id, trigger_type, text_excerpt, speaker, intensity}

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to detect emotional dynamics.

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

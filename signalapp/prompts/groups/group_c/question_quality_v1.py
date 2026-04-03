"""
Group C — Question Quality framework prompt — v1.

Evaluates question quality and diagnostic power.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field


class QuestionInstance(BaseModel):
    segment_id: str
    question_text: str
    question_type: str  # "open" | "closed" | "leading" | "rhetorical"
    diagnostic_power: str  # "high" | "medium" | "low"
    speaker: str


class QuestionQualityOutput(BaseModel):
    total_questions: int
    open_count: int
    closed_count: int
    leading_count: int
    high_diagnostic_count: int

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    question_instances: list[QuestionInstance] = Field(default_factory=list)

    weak_questions: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, issue}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to evaluate question quality.

RULES:
1. Every classification must cite verbatim text from the transcript.
2. Open questions: "what", "how", "why" — invite exploration
3. Closed questions: yes/no — limit information
4. Leading questions: suggest answer — may bias response
5. High diagnostic power: reveals buyer priorities, pain, or decision process

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

Step 1: List all questions from the rep.
Step 2: Classify each by type and diagnostic power.
Step 3: Calculate quality score.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

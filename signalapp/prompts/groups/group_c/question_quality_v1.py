"""
Group C — Question Quality framework prompt — v1.

Evaluates question quality and diagnostic power.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class QuestionQualityOutput(BaseModel):
    total_questions: int = 0
    open_count: int = 0
    high_diagnostic_count: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to evaluate question quality.

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

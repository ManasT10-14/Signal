"""
Group A — Deal Timing Intelligence framework prompt — v1.

Detects timing signals and urgency indicators.
Part of the Negotiation Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class DealTimingOutput(BaseModel):
    overall_urgency_score: float = 0.0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to identify deal timing signals.

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
2. Urgency signals: budget cycles, Q-end, competing deals, leadership changes
3. Delay signals: "need to think", "discuss with team", "next quarter"
4. Stall signals: repeated topic changes, no forward movement, vague next steps
5. Do NOT fabricate — output empty list if no signals found

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify all timing-related language.
Step 2: Classify each as urgency/delay/stall/timeline.
Step 3: Calculate urgency score.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

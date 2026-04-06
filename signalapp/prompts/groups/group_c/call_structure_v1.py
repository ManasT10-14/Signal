"""
Group C — Call Structure Analysis framework prompt — v1.

Analyzes the structural integrity of the call.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CallStructureOutput(BaseModel):
    structure_score: float = 0.0
    has_discovery: bool = False
    has_close: bool = False
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to analyze call structure.

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
2. Required phases: opening, discovery, value presentation, objection handling, close
3. Each phase must have sufficient depth (not just one line)
4. Structural issues: missing phases, disordered phases, shallow phases

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

Step 1: Identify which phases are present.
Step 2: Evaluate depth and quality of each phase.
Step 3: Identify structural issues.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

"""
Group C — Call Structure Analysis framework prompt — v1.

Analyzes the structural integrity of the call.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field


class CallStructureOutput(BaseModel):
    structure_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    has_opening: bool = False
    has_discovery: bool = False
    has_value_presentation: bool = False
    has_objection_handling: bool = False
    has_close: bool = False

    missing_phases: list[str] = Field(default_factory=list)
    structural_issues: list[dict] = Field(default_factory=list)
    # {segment_id, issue_type, description, quote}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to analyze call structure.

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

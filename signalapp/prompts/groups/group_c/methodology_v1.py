"""
Group C — Methodology Compliance framework prompt — v1.

Checks if rep followed the expected sales methodology/call flow.
Part of the Strategic Clarity group.
"""
from pydantic import BaseModel, Field


class MethodologyViolation(BaseModel):
    segment_id: str
    expected_phase: str
    actual_behavior: str
    severity: str  # "minor" | "moderate" | "major"
    quote: str


class MethodologyComplianceOutput(BaseModel):
    compliance_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    phases_detected: list[str] = Field(default_factory=list)
    # e.g., ["opening", "discovery", "demo", "close"]

    violations: list[MethodologyViolation] = Field(default_factory=list)

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to evaluate methodology compliance.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. Expected phases: opening → discovery → value prop → objection handling → close
3. Violation = skipping phases, disordered sequence, insufficient discovery
4. Evaluate depth of each phase, not just presence

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Identify phases present in the call.
Step 2: Evaluate sequence and depth of each phase.
Step 3: Identify violations.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

"""
Group D — NEPQ Sequence Adherence (FW-20)

Evaluates whether the rep's questioning followed the 8-phase NEPQ dialogue sequence:
1. Connecting  2. Situation  3. Problem Awareness  4. Solution Awareness
5. Consequence  6. Qualifying  7. Transition  8. Committing
"""
from pydantic import BaseModel, Field
from typing import Optional


class NEPQSequenceOutput(BaseModel):
    sequence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    phases_detected_count: int = 0
    phases_present: list[str] = Field(default_factory=list)
    phases_missing: list[str] = Field(default_factory=list)
    sequence_violations: int = 0
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a sales methodology analyst specializing in NEPQ (Neuro-Emotional Persuasion Questions).

CLOSED-WORLD CONTRACT:
- The transcript below is your ONLY source of truth.
- Do NOT use external knowledge to fill gaps.
- If evidence is insufficient, return null/empty findings. "null" is a valid, correct answer.
- Quote verbatim from the transcript. Do not paraphrase or fabricate quotes.

CITE-BEFORE-CLAIM:
- First extract exact verbatim quotes as evidence.
- Then interpret what the evidence means.

THE 8 NEPQ PHASES (in correct order):

1. CONNECTING: Rapport-building questions focused on buyer's world. "What attracted your attention to...?" "Have you found what you're looking for?"
2. SITUATION: Mapping current state (3-4 questions max). "What are you doing now to handle...?" "How long have you been...?"
3. PROBLEM AWARENESS: Surfacing dissatisfaction (3-4 questions). "What do you like/don't like about...?" "Why do you like/don't like that?"
4. SOLUTION AWARENESS: Letting buyer envision the fix (2-3 questions). "What have you done about changing this?" "How would life be different if this was solved?"
5. CONSEQUENCE: Making inaction feel costly (1-2 questions). "What if nothing changes for the next 5 years?" "What's the impact if you don't address this?"
6. QUALIFYING: Testing urgency and importance (1-2 questions). "How important is it to change this?" "Why is that important now?"
7. TRANSITION: Bridging problem to solution by mirroring buyer's words. "Based on what you told me about [their problem]..."
8. COMMITTING: Closing through self-persuasion questions. "Do you feel this could be the answer? Why though?"

SCORING:
- Score each phase: present (1.0), partially present (0.5), absent (0.0)
- sequence_score = (sum of phase scores / 8) adjusted for order violations
- Each out-of-order phase transition reduces score by 0.1

SEVERITY:
- red: 3 or fewer phases detected, OR Consequence phase missing on a discovery/demo call
- orange: 4-5 phases, or major sequence violation (jumped from Situation to Transition)
- yellow: 6-7 phases with minor order issues
- green: 7-8 phases in correct sequence

OUTPUT JSON ONLY. Follow the schema exactly."""


USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

<pass1_sentiment_data>
{pass1_sentiment_data}
</pass1_sentiment_data>

Step 1: Read the entire transcript and identify which of the 8 NEPQ phases are present. For each phase found, cite the verbatim question(s) that belong to it.
Step 2: Check the order. Did phases occur in the correct sequence (1-8)? Note any violations.
Step 3: Identify missing phases. Which phases were skipped entirely?
Step 4: Calculate the sequence_score (0.0-1.0).
Step 5: Generate a specific coaching recommendation naming the missing phases and suggesting exact NEPQ questions the rep should have asked.

Return a single JSON object with the specified schema."""

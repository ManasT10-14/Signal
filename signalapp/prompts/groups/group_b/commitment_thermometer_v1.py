"""
Group B — Commitment Thermometer framework prompt — v1.

Tracks buyer commitment temperature throughout the call.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field


class CommitmentReading(BaseModel):
    segment_id: str
    temperature: float = Field(ge=0.0, le=1.0)  # 0=cold, 1=hot
    indicators: list[str] = Field(default_factory=list)
    # e.g., ["specific timeline", "budget language", "authority statement"]
    quote: str


class CommitmentThermometerOutput(BaseModel):
    starting_temperature: float = Field(ge=0.0, le=1.0)
    ending_temperature: float = Field(ge=0.0, le=1.0)
    temperature_delta: float  # positive = warming, negative = cooling
    trajectory: str  # "heating" | "cooling" | "stable" | "volatile"

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    readings: list[CommitmentReading] = Field(default_factory=list)

    cold_spells: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote, cause}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your task is to track commitment temperature.

RULES:
1. Every classification must cite verbatim text from the transcript.
2. Temperature indicators: specific commitment (high), general interest (medium), deflection (low)
3. Track trajectory over the call: heating, cooling, stable, or volatile
4. Cold spell = sudden drop in temperature mid-call
5. Rate each segment or significant moment

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: Rate commitment temperature at key moments.
Step 2: Track trajectory across the call.
Step 3: Identify cold spells.
Step 4: Generate coaching recommendation.

Return a single JSON object with the specified schema.
"""

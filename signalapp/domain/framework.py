"""
Framework domain models — FrameworkOutput, FrameworkResult, etc.
These are the core data structures used throughout the pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"


def normalize_severity(val) -> str:
    """Convert any severity representation to a lowercase string.

    Accepts Severity enum, string, or any object with a .value attribute.
    """
    if isinstance(val, Severity):
        return val.value
    if hasattr(val, "value"):
        return str(val.value).lower()
    return str(val).lower()


class EvidenceType(str, Enum):
    SEGMENT = "segment"
    RANGE = "range"


@dataclass
class EvidenceRef:
    """Reference to transcript evidence."""

    segment_id: str
    start_time_ms: int
    end_time_ms: int
    speaker: str
    text_excerpt: str
    evidence_type: EvidenceType = EvidenceType.SEGMENT


class FrameworkOutput(BaseModel):
    """Output from a single framework analysis."""

    framework_id: str  # e.g., "FW-01-101"
    framework_name: str  # e.g., "Unanswered Questions"
    score: Optional[float] = Field(default=None, ge=0, le=100)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)  # Flexible dict format for evidence
    coaching_recommendation: str
    raw_analysis: dict = Field(default_factory=dict)
    # AIM output (when framework runs due to AIM but finds nothing)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None  # e.g., "No alternatives detected — weak BATNA"


@dataclass
class FrameworkResult:
    """Stored result of a framework run."""

    framework_id: str
    framework_version: str
    prompt_version: str
    model_used: str
    model_version: str
    prompt_group: str  # "A" | "B" | "C" | "D" | "E"
    score: Optional[float]
    severity: str
    confidence: float
    headline: str
    explanation: str
    evidence: list[dict]  # JSONB
    coaching_recommendation: str
    raw_output: dict  # Full LLM response JSONB
    tokens_input: int
    tokens_output: int
    latency_ms: int
    cost_usd: float


# Framework metadata registry
FRAMEWORK_REGISTRY: dict[int, dict] = {
    1: {
        "name": "Unanswered Questions",
        "group": "B",
        "prompt_file": "group_b/unanswered_questions_v1",
        "severity_threshold": 0.65,
    },
    2: {
        "name": "Commitment Quality",
        "group": "B",
        "prompt_file": "group_b/commitment_quality_v1",
        "severity_threshold": 0.65,
    },
    3: {
        "name": "BATNA Detection",
        "group": "A",
        "prompt_file": "group_a/batna_detection_v1",
        "severity_threshold": 0.70,
        "is_scaffolded": True,  # Per PRD Section 14
    },
    4: {
        "name": "Money Left on Table",
        "group": "A",
        "prompt_file": "group_a/money_left_on_table_v1",
        "severity_threshold": 0.70,
    },
    5: {
        "name": "Question Quality",
        "group": "C",
        "prompt_file": "group_c/question_quality_v1",
        "severity_threshold": 0.65,
    },
    6: {
        "name": "Commitment Thermometer",
        "group": "B",
        "prompt_file": "group_b/commitment_thermometer_v1",
        "severity_threshold": 0.65,
    },
    7: {
        "name": "First Number Tracker",
        "group": "A",
        "prompt_file": "group_a/first_number_tracker_v1",
        "severity_threshold": 0.65,
        "is_scaffolded": True,
    },
    8: {
        "name": "Emotional Turning Points",
        "group": "E",
        "prompt_file": "group_e/emotional_turning_points_v1",
        "severity_threshold": 0.65,
        "is_pinned": True,
    },
    9: {
        "name": "Emotional Trigger Analysis",
        "group": "E",
        "prompt_file": "group_e/emotional_turning_points_v1",  # Combined with 8
        "severity_threshold": 0.60,
        "is_pinned": True,
    },
    10: {
        "name": "Frame Match Score",
        "group": "C",
        "prompt_file": "group_c/frame_match_v1",
        "severity_threshold": 0.75,
    },
    11: {
        "name": "Close Attempt Analysis",
        "group": "C",
        "prompt_file": "group_c/close_attempt_v1",
        "severity_threshold": 0.70,
        "is_scaffolded": True,  # Phase 2
    },
    12: {
        "name": "Deal Health at Close",
        "group": "A",
        "prompt_file": "group_a/deal_health_v1",
        "severity_threshold": 0.70,
        "is_scaffolded": True,
    },
    13: {
        "name": "Deal Timing Intelligence",
        "group": "A",
        "prompt_file": "group_a/deal_timing_v1",
        "severity_threshold": 0.65,
        "is_scaffolded": True,
    },
    14: {
        "name": "Methodology Compliance",
        "group": "C",
        "prompt_file": "group_c/methodology_v1",
        "severity_threshold": 0.65,
        "is_scaffolded": True,
    },
    15: {
        "name": "Call Structure Analysis",
        "group": "C",
        "prompt_file": "group_c/call_structure_v1",
        "severity_threshold": 0.70,
        "is_pinned": True,
    },
    16: {
        "name": "Pushback Classification",
        "group": "B",
        "prompt_file": "group_b/pushback_classification_v1",
        "severity_threshold": 0.70,
    },
    17: {
        "name": "Objection Response Score",
        "group": "C",
        "prompt_file": "group_c/objection_response_v1",
        "severity_threshold": 0.70,
    },
    # Group D — NEPQ Methodology Intelligence
    20: {
        "name": "NEPQ Sequence Adherence",
        "group": "D",
        "prompt_file": "group_d/nepq_sequence_v1",
        "severity_threshold": 0.65,
    },
    21: {
        "name": "Diagnostic Depth",
        "group": "D",
        "prompt_file": "group_d/diagnostic_depth_v1",
        "severity_threshold": 0.65,
    },
    22: {
        "name": "Self-Generated Commitment",
        "group": "D",
        "prompt_file": "group_d/self_generated_commitment_v1",
        "severity_threshold": 0.70,
    },
}

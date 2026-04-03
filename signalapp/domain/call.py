"""
Call aggregate root — the central entity.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CallType(str, Enum):
    DISCOVERY = "discovery"
    DEMO = "demo"
    PRICING = "pricing"
    NEGOTIATION = "negotiation"
    CLOSE = "close"
    CHECK_IN = "check_in"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class Call:
    """Call aggregate root — the primary entity."""

    call_id: str
    org_id: str
    uploaded_by: str
    rep_name: str
    call_type: CallType
    deal_name: Optional[str] = None
    call_date: Optional[str] = None
    duration_seconds: Optional[int] = None
    audio_s3_key: Optional[str] = None
    input_type: str = "audio"  # "audio" | "paste"
    processing_status: ProcessingStatus = ProcessingStatus.PROCESSING
    notes: Optional[str] = None
    created_at: str = ""

    # Computed properties
    @property
    def duration_minutes(self) -> float:
        if self.duration_seconds is None:
            return 0.0
        return self.duration_seconds / 60.0

    @property
    def is_short_call(self) -> bool:
        return self.duration_minutes < 8.0 if self.duration_minutes else False


class Pass1Result(BaseModel):
    """
    Pass 1 infrastructure extraction result.
    Stored as JSONB in the database.
    """

    pass1_result_id: str
    analysis_run_id: str
    # Hedge detection
    hedge_data: list[dict] = Field(default_factory=list)
    # Sentiment trajectory
    sentiment_data: list[dict] = Field(default_factory=list)
    # Evaluative language
    appraisal_data: list[dict] = Field(default_factory=list)
    # Metadata
    prompt_version: str = "v1"
    model_used: str = "gemini"
    model_version: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    created_at: str = ""

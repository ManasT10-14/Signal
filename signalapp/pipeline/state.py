"""
LangGraph Pipeline State — TypedDict schema for LangGraph StateGraph.

LangGraph's StateGraph uses this TypedDict to define the state schema.
Each node returns a dict with only the fields it updates; LangGraph merges them.
"""
from __future__ import annotations

from typing import TypedDict, Optional


class PipelineState(TypedDict, total=False):
    """
    LangGraph workflow state schema.
    Each node reads what it needs and writes its output.

    All domain objects are stored as serialized dicts for LangGraph compatibility.
    """

    # Immutable input
    call_id: str
    call_type: str  # "discovery" | "demo" | "pricing" | ...
    transcript_segments: list[dict]  # Serialized TranscriptSegment dicts

    # Base metrics (zero LLM cost)
    base_metrics: dict | None

    # Pass 1
    pass1_result: dict | None  # Serialized Pass1Result

    # Routing
    routing_decisions: list[dict]  # Serialized RoutingDecision dicts
    active_frameworks: set[int]
    pass1_gate_signals: dict | None  # Serialized Pass1GateSignals dict

    # Framework results
    framework_results: dict[int, dict]  # fw_id → FrameworkOutput dict
    framework_errors: dict[int, str]

    # Verified insights
    verified_insights: list[dict]  # Serialized Insight dicts

    # Summary
    summary: dict | None

    # Segment-level coaching
    segment_coaching: dict | None

    # Errors
    errors: list[str]

    # Internal-only fields (not part of core state, used for flow control)
    _active_groups: list[str]  # Which groups have active frameworks
    _verification_flags: list[dict]  # Verification gate results

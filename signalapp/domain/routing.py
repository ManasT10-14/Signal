"""
Framework routing — pure Python decision engine.
Implements the routing table from FRAMEWORK_ROUTING_ARCHITECTURE.md.
Zero cost: routing decisions use metadata + Pass 1 output, no LLM calls.
"""
from __future__ import annotations
from dataclasses import dataclass, field


CALL_TYPES = {"discovery", "demo", "pricing", "negotiation", "close", "check_in", "other"}

PINNED_FRAMEWORKS = {8, 9, 15}  # Emotional Turning Points + Emotion Trigger + Call Structure


@dataclass
class Pass1GateSignals:
    """Derived from Pass 1 output. No additional LLM calls needed."""

    has_competitor_mention: bool = False
    has_pricing_discussion: bool = False
    has_numeric_anchor: bool = False
    has_objection_markers: bool = False
    has_rep_questions: bool = False
    has_close_language: bool = False
    call_duration_minutes: float = 0.0


@dataclass
class FrameworkRoutingSpec:
    """Routing specification for a single framework."""

    fw_id: int
    mandatory_for: set[str] = field(default_factory=set)
    blocked_for: set[str] = field(default_factory=set)
    required_signal: str | None = None
    is_pinned: bool = False


# Routing table — 17 Phase 1 frameworks
ROUTING_TABLE: dict[int, FrameworkRoutingSpec] = {
    # Universal frameworks — always run on all call types
    1: FrameworkRoutingSpec(fw_id=1),  # Unanswered Questions
    2: FrameworkRoutingSpec(fw_id=2),  # Commitment Quality
    6: FrameworkRoutingSpec(fw_id=6),  # Commitment Thermometer
    # PINNED frameworks
    8: FrameworkRoutingSpec(fw_id=8, is_pinned=True),  # Emotional Turning Points
    9: FrameworkRoutingSpec(fw_id=9, is_pinned=True),  # Emotion Trigger (combined with 8)
    15: FrameworkRoutingSpec(fw_id=15, is_pinned=True),  # Call Structure
    # AIM frameworks
    3: FrameworkRoutingSpec(  # BATNA Detection
        fw_id=3,
        mandatory_for={"pricing", "negotiation", "close"},
        blocked_for={"check_in"},
        required_signal="has_competitor_mention",
    ),
    4: FrameworkRoutingSpec(  # Money Left on Table
        fw_id=4,
        mandatory_for={"pricing", "negotiation"},
        blocked_for={"discovery", "demo", "check_in"},
        required_signal="has_pricing_discussion",
    ),
    5: FrameworkRoutingSpec(  # Question Quality
        fw_id=5,
        required_signal="has_rep_questions",
    ),
    7: FrameworkRoutingSpec(  # First Number Tracker
        fw_id=7,
        mandatory_for={"pricing", "negotiation"},
        blocked_for={"discovery", "demo", "check_in"},
        required_signal="has_numeric_anchor",
    ),
    10: FrameworkRoutingSpec(  # Frame Match Score
        fw_id=10,
        blocked_for={"check_in"},
    ),
    11: FrameworkRoutingSpec(  # Close Attempt Analysis
        fw_id=11,
        mandatory_for={"demo", "pricing", "negotiation", "close"},
        blocked_for={"check_in"},
        required_signal="has_close_language",
    ),
    12: FrameworkRoutingSpec(  # Deal Health at Close
        fw_id=12,
        mandatory_for={"negotiation", "close"},
        blocked_for={"discovery", "demo", "check_in"},
        required_signal="has_close_language",
    ),
    13: FrameworkRoutingSpec(  # Deal Timing Intelligence
        fw_id=13,
        mandatory_for={"discovery", "demo"},
        blocked_for={"pricing", "negotiation", "close", "check_in"},
    ),
    14: FrameworkRoutingSpec(  # Methodology Compliance (dependency-gated)
        fw_id=14,
        blocked_for={"check_in"},
    ),
    16: FrameworkRoutingSpec(  # Pushback Classification
        fw_id=16,
        blocked_for={"check_in"},
        required_signal="has_objection_markers",
    ),
    17: FrameworkRoutingSpec(  # Objection Response Score (dependency-gated)
        fw_id=17,
        blocked_for={"check_in"},
    ),
    # ── Group D — NEPQ Methodology Intelligence (Phase 2) ──
    20: FrameworkRoutingSpec(  # NEPQ Sequence Adherence
        fw_id=20,
        mandatory_for={"discovery", "demo"},
        blocked_for={"check_in"},
        required_signal="has_rep_questions",
    ),
    21: FrameworkRoutingSpec(  # Diagnostic Depth
        fw_id=21,
        mandatory_for={"discovery"},
        blocked_for={"check_in"},
        required_signal="has_rep_questions",
    ),
    22: FrameworkRoutingSpec(  # Self-Generated Commitment
        fw_id=22,
        mandatory_for={"demo", "pricing", "negotiation", "close"},
        blocked_for={"check_in"},
        required_signal="has_close_language",
    ),
}

# Framework → prompt group membership
GROUP_MEMBERSHIP: dict[str, set[int]] = {
    "A": {3, 4, 7, 12, 13},
    "B": {1, 2, 6, 16},
    "C": {5, 10, 11, 14, 15, 17},
    "D": {20, 21, 22},  # Methodology Intelligence (NEPQ)
    "E": {8, 9},
}

# Dependency rules: (dependent_fw_id, required_fw_ids)
DEPENDENCY_RULES: list[tuple[int, set[int]]] = [
    (9, {8}),  # Emotion Trigger requires Emotional Turning Points
    (14, {5, 15}),  # Methodology requires Question Quality + Call Structure
    (17, {16}),  # Objection Response requires Pushback Classification
    (20, {15}),  # NEPQ Sequence requires Call Structure
    (22, {2}),  # Self-Generated Commitment requires Commitment Quality
]


@dataclass
class RoutingDecision:
    fw_id: int
    decision: str  # "RUN" | "BLOCK" | "SKIP_EMPTY"
    reason: str
    is_aim: bool = False


def should_run_framework(
    fw_id: int,
    call_type: str,
    signals: Pass1GateSignals,
) -> RoutingDecision:
    """
    Decide whether a framework should run for a given call.
    Returns a RoutingDecision with the decision and reason.
    """
    # Unknown call types default to treating all frameworks as universal
    effective_call_type = call_type if call_type in CALL_TYPES else "other"

    spec = ROUTING_TABLE.get(fw_id)
    if spec is None:
        return RoutingDecision(fw_id=fw_id, decision="BLOCK", reason="Unknown framework")

    # Pinned frameworks always run
    if fw_id in PINNED_FRAMEWORKS or spec.is_pinned:
        return RoutingDecision(
            fw_id=fw_id, decision="RUN", reason="Pinned framework — always runs"
        )

    # Blocked call types
    if effective_call_type in spec.blocked_for:
        return RoutingDecision(
            fw_id=fw_id,
            decision="BLOCK",
            reason=f"Call type '{effective_call_type}' blocks this framework",
        )

    # Mandatory call types — AIM: run even without content signal
    if effective_call_type in spec.mandatory_for:
        return RoutingDecision(
            fw_id=fw_id,
            decision="RUN",
            reason=f"AIM: mandatory on {effective_call_type} — absence is meaningful",
            is_aim=True,
        )

    # Content-gated: check Pass 1 signal
    if spec.required_signal:
        signal_value = getattr(signals, spec.required_signal, False)
        if not signal_value:
            return RoutingDecision(
                fw_id=fw_id,
                decision="BLOCK",
                reason=f"Content gate: {spec.required_signal}=False, no signal detected",
            )

    return RoutingDecision(fw_id=fw_id, decision="RUN", reason="Universal framework")


def should_run_framework_safe(
    fw_id: int, call_type: str, signals: Pass1GateSignals
) -> bool:
    """Fail-open wrapper: routing error → include the framework."""
    try:
        decision = should_run_framework(fw_id, call_type, signals)
        return decision.decision == "RUN"
    except Exception:
        return True  # Fail open — better to run extra framework than miss insight


def enforce_dependencies(
    active: set[int], signals: Pass1GateSignals
) -> set[int]:
    """
    Enforce framework dependencies.
    - Add pinned frameworks
    - Remove dependents whose requirements aren't met
    - Handle cascade (if A requires B, and B requires C, removing C removes A too)
    """
    # Always add pinned frameworks
    active = active | PINNED_FRAMEWORKS

    # Iteratively remove dependents with unmet requirements
    changed = True
    while changed:
        changed = False
        for dependent, requirements in DEPENDENCY_RULES:
            if dependent in active and not requirements.issubset(active):
                active.discard(dependent)
                changed = True

    # Short call guard: structure/methodology need sufficient content
    if signals.call_duration_minutes < 8:
        active -= {13, 14}
        # #15 (Call Structure) is pinned — never removed even for short calls

    return active


def route_frameworks(
    call_type: str,
    signals: Pass1GateSignals,
    all_frameworks: set[int] | None = None,
) -> tuple[set[int], list[RoutingDecision]]:
    """
    Main routing function: decide which frameworks run for a call.
    Returns (active_framework_ids, routing_decisions).
    """
    if all_frameworks is None:
        all_frameworks = set(range(1, 18)) | {20, 21, 22}

    decisions = []
    active = set()

    for fw_id in sorted(all_frameworks):
        decision = should_run_framework(fw_id, call_type, signals)
        decisions.append(decision)
        if decision.decision == "RUN":
            active.add(fw_id)

    # Enforce dependencies
    active = enforce_dependencies(active, signals)

    return active, decisions


def get_active_groups(active_frameworks: set[int]) -> list[str]:
    """
    Given a set of active framework IDs, return which groups have survivors.
    Empty groups are skipped.
    """
    return [
        group_id
        for group_id, members in GROUP_MEMBERSHIP.items()
        if active_frameworks & members  # intersection
    ]

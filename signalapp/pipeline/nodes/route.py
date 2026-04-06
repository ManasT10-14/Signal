"""
Framework routing node — pure Python decision engine.
Zero LLM cost: routing uses metadata + Pass 1 output signals.
"""
from __future__ import annotations

from signalapp.pipeline.state import PipelineState
from signalapp.domain.routing import route_frameworks, get_active_groups, RoutingDecision, Pass1GateSignals


async def route_node(state: PipelineState) -> dict:
    """
    Route frameworks based on call type and Pass 1 gate signals.

    Inputs: call_type, pass1_result, pass1_gate_signals (dict)
    Outputs: routing_decisions (list of dicts), active_frameworks

    This is a pure Python node — no LLM calls.
    """
    from signalapp.domain.routing import route_frameworks, get_active_groups

    call_type = state["call_type"]
    signals_dict = state.get("pass1_gate_signals")

    if signals_dict is None:
        # If Pass1 failed, use empty signals (fail-open — run all universal)
        signals = Pass1GateSignals()
    else:
        # Deserialize dict back to Pass1GateSignals
        signals = Pass1GateSignals(**signals_dict)

    # Run routing
    active_frameworks, decisions = route_frameworks(
        call_type=call_type,
        signals=signals,
    )

    # Get active groups for fan-out
    active_groups = get_active_groups(active_frameworks)

    # Serialize RoutingDecision objects to dicts for TypedDict compatibility
    serialized_decisions = [
        {"fw_id": d.fw_id, "decision": d.decision, "reason": d.reason, "is_aim": d.is_aim}
        for d in decisions
    ]

    return {
        "routing_decisions": serialized_decisions,
        "active_frameworks": active_frameworks,
        # Also store which groups to execute (used by execute_groups node)
        "_active_groups": active_groups,
    }

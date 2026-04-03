"""
Insight generation node — prioritizes and formats insights from framework results.

Takes verified framework results, applies prioritization logic,
and produces ranked insights ready for user display.
"""
from __future__ import annotations

from signalapp.pipeline.state import PipelineState


# Severity rank for sorting (lower = more important)
SEVERITY_RANK = {"red": 0, "orange": 1, "yellow": 2, "green": 3}


async def generate_insights_node(state: PipelineState) -> dict:
    """
    Generate prioritized insights from verified framework results.

    Inputs: verified_insights (list of dicts), framework_results, pass1_gate_signals
    Outputs: verified_insights (ranked and prioritized dicts)

    Applies severity → confidence → actionability sorting.
    Marks top 5 insights and assigns priority ranks.
    """
    verified_insights = state.get("verified_insights") or []

    if not verified_insights:
        return {"verified_insights": []}

    # Sort by severity rank then by confidence descending
    def sort_key(insight: dict) -> tuple:
        sev = insight.get("severity", "green").lower()
        conf = insight.get("confidence", 0.0)
        return (SEVERITY_RANK.get(sev, 99), -conf)

    sorted_insights = sorted(verified_insights, key=sort_key)

    # Assign priority ranks and top_insight flag
    for idx, insight in enumerate(sorted_insights[:5]):
        insight["priority_rank"] = idx + 1
        insight["is_top_insight"] = True

    for idx, insight in enumerate(sorted_insights[5:]):
        insight["priority_rank"] = 5 + idx + 1
        insight["is_top_insight"] = False

    return {"verified_insights": sorted_insights}

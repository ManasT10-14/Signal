"""
Insight generation node — prioritizes and formats insights from framework results.

Takes verified framework results, applies prioritization logic,
and produces ranked insights ready for user display.
Preserves AIM (Absence Is Meaningful) findings.
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

    Applies severity -> confidence -> actionability sorting.
    Marks top 5 insights and assigns priority ranks.
    Preserves AIM null findings (don't suppress them).
    """
    verified_insights = state.get("verified_insights") or []

    # Filter out stubs from failed LLM calls (defense in depth)
    verified_insights = [
        i for i in verified_insights
        if i.get("headline") != "Analysis unavailable"
        and (i.get("confidence", 0.0) > 0.0 or i.get("is_aim_null_finding"))
    ]

    if not verified_insights:
        return {"verified_insights": []}

    # Separate AIM findings and regular insights for prioritization
    aim_findings = [i for i in verified_insights if i.get("is_aim_null_finding")]
    regular_insights = [i for i in verified_insights if not i.get("is_aim_null_finding")]

    # Sort regular insights by severity rank then by confidence descending
    def sort_key(insight: dict) -> tuple:
        sev = insight.get("severity", "green").lower()
        conf = insight.get("confidence", 0.0)
        return (SEVERITY_RANK.get(sev, 99), -conf)

    sorted_regular = sorted(regular_insights, key=sort_key)
    sorted_aim = sorted(aim_findings, key=sort_key)

    # Merge: regular insights first, then AIM findings
    all_sorted = sorted_regular + sorted_aim

    # Assign priority ranks and top_insight flag
    for idx, insight in enumerate(all_sorted[:5]):
        insight["priority_rank"] = idx + 1
        insight["is_top_insight"] = True

    for idx, insight in enumerate(all_sorted[5:]):
        insight["priority_rank"] = 5 + idx + 1
        insight["is_top_insight"] = False

    return {"verified_insights": all_sorted}

"""
Summary generation node — AI-powered structured call summary.

Generates structured sections: RECAP, KEY DECISIONS, ACTION ITEMS,
OPEN QUESTIONS, DEAL ASSESSMENT — per PRD specification.
"""
from __future__ import annotations

import logging
from signalapp.pipeline.state import PipelineState
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StructuredSummaryOutput(BaseModel):
    """Output schema for structured LLM summary."""
    recap: str = Field(description="Brief 2-3 sentence overview of the call")
    key_decisions: list[str] = Field(default_factory=list, description="Pricing changes, agreements made")
    action_items_rep: list[str] = Field(default_factory=list, description="Tasks for the rep")
    action_items_buyer: list[str] = Field(default_factory=list, description="Tasks for the buyer")
    open_questions: list[str] = Field(default_factory=list, description="Unresolved items")
    deal_assessment: str = Field(description="Risk assessment of the deal")
    coaching_focus: str = Field(description="Primary coaching opportunity")


async def generate_summary_node(state: PipelineState) -> dict:
    """
    Generate structured AI summary from framework results and insights.

    Inputs: call_id, verified_insights, framework_results, pass1_result, base_metrics
    Outputs: summary dict with structured sections
    """
    from signalapp.app.config import get_config
    from signalapp.domain.framework import normalize_severity

    verified_insights = state.get("verified_insights") or []
    framework_results = state.get("framework_results") or {}
    pass1_result = state.get("pass1_result") or {}
    base_metrics = state.get("base_metrics") or {}
    call_id = state["call_id"]
    call_type = state.get("call_type", "other")

    # SPIN data derived by Pass 1 — surfaced to UI and used for coaching
    spin_counts = pass1_result.get("spin_counts") or {"S": 0, "P": 0, "I": 0, "N": 0}
    spin_ratio = float(pass1_result.get("spin_ratio") or 0.0)
    spin_questions = pass1_result.get("spin_questions") or []
    spin_block = {
        "counts": spin_counts,
        "ratio": spin_ratio,
        "total": sum(spin_counts.values()),
        "sample_questions": spin_questions[:6],
        "applicable": call_type in ("discovery", "demo") and sum(spin_counts.values()) >= 3,
    }

    config = get_config()

    top_insights = [i for i in verified_insights if i.get("is_top_insight", False)][:5]

    # Extract severity breakdown
    severity_counts = {"red": 0, "orange": 0, "yellow": 0, "green": 0}
    for insight in verified_insights:
        sev = normalize_severity(insight.get("severity", "green"))
        if sev in severity_counts:
            severity_counts[sev] += 1

    # Try LLM-powered structured summary
    structured = None
    try:
        structured = await _generate_structured_summary(
            insights=top_insights,
            severity_counts=severity_counts,
            framework_results=framework_results,
            pass1_result=pass1_result,
            base_metrics=base_metrics,
            config=config,
        )
    except Exception as e:
        logger.warning(f"[summary] LLM summary failed: {e}. Using fallback.")

    # Build summary structure
    if structured:
        coaching_focus = structured.coaching_focus
        spin_note = _spin_coaching_note(spin_block, call_type)
        if spin_note:
            coaching_focus = (coaching_focus + "\n\n" + spin_note).strip() if coaching_focus else spin_note
        summary = {
            "call_id": call_id,
            "headline": _generate_headline(severity_counts),
            "recap": structured.recap,
            "key_decisions": structured.key_decisions,
            "action_items_rep": structured.action_items_rep,
            "action_items_buyer": structured.action_items_buyer,
            "open_questions": structured.open_questions,
            "deal_assessment": structured.deal_assessment,
            "coaching_focus": coaching_focus,
            "key_themes": [i.get("headline", "") for i in top_insights[:3] if i.get("headline")],
            "top_insight": top_insights[0].get("headline", "No significant insights") if top_insights else "No significant insights",
            "severity_breakdown": severity_counts,
            "total_insights": len(verified_insights),
            "frameworks_run": list(framework_results.keys()) if framework_results else [],
            "ai_summary_text": structured.recap,
            "base_metrics": base_metrics,
            "spin": spin_block,
        }
    else:
        # Fallback
        fallback_text = _generate_fallback_summary(verified_insights, top_insights, severity_counts)
        coaching_focus = top_insights[0].get("coaching_recommendation", "")[:200] if top_insights else ""
        spin_note = _spin_coaching_note(spin_block, call_type)
        if spin_note:
            coaching_focus = (coaching_focus + "\n\n" + spin_note).strip() if coaching_focus else spin_note
        summary = {
            "call_id": call_id,
            "headline": _generate_headline(severity_counts),
            "recap": fallback_text,
            "key_decisions": [],
            "action_items_rep": [],
            "action_items_buyer": [],
            "open_questions": _extract_open_questions(verified_insights),
            "deal_assessment": _assess_deal_from_severity(severity_counts),
            "coaching_focus": coaching_focus,
            "key_themes": [i.get("headline", "") for i in top_insights[:3] if i.get("headline")],
            "top_insight": top_insights[0].get("headline", "No significant insights") if top_insights else "No significant insights",
            "severity_breakdown": severity_counts,
            "total_insights": len(verified_insights),
            "frameworks_run": list(framework_results.keys()) if framework_results else [],
            "ai_summary_text": fallback_text,
            "base_metrics": base_metrics,
            "spin": spin_block,
        }

    return {"summary": summary}


async def _generate_structured_summary(
    insights: list[dict],
    severity_counts: dict,
    framework_results: dict,
    pass1_result: dict,
    base_metrics: dict,
    config,
) -> StructuredSummaryOutput:
    """Generate a structured summary using LLM."""
    import os
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not (gemini_key or gcp_project):
        raise RuntimeError("No LLM credentials configured")

    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig

    insights_text = ""
    for i, insight in enumerate(insights, 1):
        insights_text += f"""
{i}. [{insight.get('severity', 'unknown').upper()}] {insight.get('framework_name', 'Unknown')}
   Headline: {insight.get('headline', 'N/A')}
   Explanation: {insight.get('explanation', 'N/A')}
   Coaching: {insight.get('coaching_recommendation', 'N/A')}
"""

    # Base metrics context
    metrics_text = ""
    if base_metrics:
        metrics_text = f"""
Base Metrics:
  Talk ratio: Rep {base_metrics.get('rep_talk_ratio', 0):.0%} / Buyer {base_metrics.get('buyer_talk_ratio', 0):.0%}
  Rep WPM: {base_metrics.get('rep_wpm', 0)} / Buyer WPM: {base_metrics.get('buyer_wpm', 0)}
  Questions: Rep {base_metrics.get('rep_questions', 0)} / Buyer {base_metrics.get('buyer_questions', 0)}
  Interruptions: {base_metrics.get('interruption_count', 0)}
"""

    sentiment_trajectory = pass1_result.get("sentiment_data", [])
    overall_sentiment = "neutral"
    if sentiment_trajectory:
        scores = [s.get("intensity", 0.5) for s in sentiment_trajectory]
        avg = sum(scores) / len(scores) if scores else 0.5
        if avg > 0.6:
            overall_sentiment = "positive"
        elif avg < 0.4:
            overall_sentiment = "negative"

    system_prompt = """You are a senior sales analyst providing a structured call summary.

RULES:
1. Be specific — cite actual behavioral patterns observed
2. Be actionable — focus on what should happen next
3. Be balanced — acknowledge positives and concerns
4. Use plain language
5. OUTPUT JSON ONLY following the exact schema."""

    user_prompt = f"""
Call Analysis Summary
=====================

Framework Insights ({len(insights)} top insights):
{insights_text if insights_text else "No insights generated."}

{metrics_text}

Overall Sentiment: {overall_sentiment}
Severity Breakdown: red={severity_counts.get('red', 0)}, orange={severity_counts.get('orange', 0)}, yellow={severity_counts.get('yellow', 0)}, green={severity_counts.get('green', 0)}

Generate a structured summary with all required fields."""

    provider = GeminiProvider()
    llm_config = LLMConfig(
        model=config.llm_pass1.model,
        temperature=0.25,
        max_tokens=config.llm_pass1.max_tokens,
        provider="gemini",
    )

    return await provider.complete_structured(
        prompt=f"{system_prompt}\n\n{user_prompt}",
        response_model=StructuredSummaryOutput,
        config=llm_config,
    )


def _generate_fallback_summary(verified_insights, top_insights, severity_counts) -> str:
    red = severity_counts.get("red", 0)
    orange = severity_counts.get("orange", 0)
    parts = []

    if red >= 2:
        parts.append("High-risk call with multiple critical behavioral issues detected.")
    elif red == 1:
        parts.append("Call has one critical issue requiring immediate attention.")
    elif orange >= 2:
        parts.append("Moderate-risk call with engagement gaps identified.")
    elif orange == 1:
        parts.append("Call has some areas for coaching improvement.")
    else:
        parts.append("Call dynamics appear generally positive with no critical behavioral flags.")

    if top_insights:
        reco = top_insights[0].get("coaching_recommendation", "")[:150]
        if reco:
            parts.append(f"Primary coaching opportunity: {reco}")

    return " ".join(parts)


def _generate_headline(severity_counts: dict) -> str:
    red = severity_counts.get("red", 0)
    orange = severity_counts.get("orange", 0)

    if red >= 2:
        return "High-risk call with multiple critical issues"
    elif red == 1:
        return "Call with one critical issue requiring attention"
    elif orange >= 2:
        return "Moderate-risk call with engagement gaps"
    elif orange == 1:
        return "Call with some areas for improvement"
    else:
        return "Generally positive call dynamics"


def _extract_open_questions(insights: list[dict]) -> list[str]:
    """Extract open questions from Unanswered Questions framework (FW-01)."""
    for insight in insights:
        if "unanswered" in insight.get("framework_name", "").lower():
            raw = insight.get("evidence", [])
            return [e.get("quote", "")[:100] for e in raw[:5] if e.get("quote")]
    return []


def _spin_coaching_note(spin_block: dict, call_type: str) -> str:
    """Generate a SPIN coaching line when the rep's question mix is weak.

    Only applies to discovery/demo calls with enough classified questions to be meaningful.
    Rackham's finding: top reps invert the S+P / I+N ratio. If ratio < 0.5, flag it.
    """
    if not spin_block or not spin_block.get("applicable"):
        return ""
    counts = spin_block.get("counts") or {}
    ratio = float(spin_block.get("ratio") or 0.0)
    s = counts.get("S", 0)
    p = counts.get("P", 0)
    i = counts.get("I", 0)
    n = counts.get("N", 0)
    total = spin_block.get("total", 0)
    if total < 3:
        return ""
    if ratio < 0.5:
        return (
            f"SPIN (Rackham): Rep asked {s} Situation + {p} Problem questions but only "
            f"{i} Implication + {n} Need-payoff (ratio {ratio:.2f}). Huthwaite's 35,000-call study "
            f"found top reps invert this — they minimize Situation questions and lean on Implication "
            f"(amplify consequences) and Need-payoff (let the buyer articulate value). Try one of: "
            f"'What happens to [buyer's pain] if this continues for another quarter?' or "
            f"'If we eliminated [specific friction], what would that free you up to do?'"
        )
    if i == 0 and n == 0:
        return (
            f"SPIN (Rackham): Rep asked {total} questions but zero Implication or Need-payoff. "
            f"The buyer never got to articulate consequences or value in their own words — "
            f"this correlates with weaker commitment at close."
        )
    return ""


def _assess_deal_from_severity(severity_counts: dict) -> str:
    red = severity_counts.get("red", 0)
    orange = severity_counts.get("orange", 0)
    if red >= 2:
        return "High risk — multiple critical issues suggest deal may stall without intervention"
    elif red == 1:
        return "Moderate risk — one critical issue needs immediate attention"
    elif orange >= 2:
        return "Cautious — several areas need coaching before next interaction"
    elif orange == 1:
        return "Progressing — minor coaching opportunities identified"
    return "Healthy — no significant behavioral concerns detected"

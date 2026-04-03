"""
Summary generation node — AI-powered call summary.

Uses a separate LLM call to generate a high-level summary of the call
from the framework results and verified insights. This is the human-readable
overview shown at the top of the call review page.
"""
from __future__ import annotations

import json
from signalapp.pipeline.state import PipelineState


async def generate_summary_node(state: PipelineState) -> dict:
    """
    Generate AI summary from framework results and insights.

    Inputs: call_id, verified_insights, framework_results, pass1_result
    Outputs: summary (dict with headline, key_themes, next_steps)

    Uses a dedicated LLM call for narrative summary generation.
    Falls back to template-based summary if LLM call fails.
    """
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig
    from pydantic import BaseModel, Field
    from typing import Optional

    verified_insights = state.get("verified_insights") or []
    framework_results = state.get("framework_results") or {}
    pass1_result = state.get("pass1_result") or {}
    call_id = state["call_id"]

    config = get_config()

    # Build structured input for the LLM
    top_insights = [i for i in verified_insights if i.get("is_top_insight", False)][:5]

    # Extract severity breakdown
    severity_counts = {"red": 0, "orange": 0, "yellow": 0, "green": 0}
    for insight in verified_insights:
        sev = insight.get("severity", "green").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    # Try LLM-powered summary
    try:
        summary_text = await _generate_llm_summary(
            insights=top_insights,
            severity_counts=severity_counts,
            framework_results=framework_results,
            pass1_result=pass1_result,
            config=config,
        )
    except Exception as e:
        # Fallback to template-based summary
        summary_text = _generate_fallback_summary(verified_insights, top_insights, severity_counts)

    # Build summary structure
    summary = {
        "call_id": call_id,
        "headline": _generate_headline(severity_counts),
        "key_themes": [i.get("headline", "") for i in top_insights[:3] if i.get("headline")],
        "top_insight": top_insights[0].get("headline", "No significant insights") if top_insights else "No significant insights",
        "severity_breakdown": severity_counts,
        "total_insights": len(verified_insights),
        "frameworks_run": list(framework_results.keys()) if framework_results else [],
        "ai_summary_text": summary_text,
    }

    return {"summary": summary}


class SummaryOutput(BaseModel):
    """Output schema for LLM summary generation."""
    summary_paragraph: str = Field(max_length=500)
    key_observations: list[str] = Field(max_length=5)
    recommended_focus: str = Field(max_length=200)


async def _generate_llm_summary(
    insights: list[dict],
    severity_counts: dict,
    framework_results: dict,
    pass1_result: dict,
    config,
) -> str:
    """Generate a narrative summary using LLM."""
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig

    # Format insights for the prompt
    insights_text = ""
    for i, insight in enumerate(insights, 1):
        insights_text += f"""
{i}. [{insight.get('severity', 'unknown').upper()}] {insight.get('framework_name', 'Unknown')}
   Headline: {insight.get('headline', 'N/A')}
   Explanation: {insight.get('explanation', 'N/A')}
   Coaching: {insight.get('coaching_recommendation', 'N/A')}
"""

    # Get sentiment from pass1
    sentiment_trajectory = pass1_result.get("sentiment_data", [])
    overall_sentiment = "neutral"
    if sentiment_trajectory:
        scores = [s.get("sentiment_score", 0) for s in sentiment_trajectory]
        avg = sum(scores) / len(scores) if scores else 0
        if avg > 0.3:
            overall_sentiment = "positive"
        elif avg < -0.3:
            overall_sentiment = "negative"

    system_prompt = """You are a senior sales analyst providing a concise call summary.
Your task is to synthesize framework analysis results into a narrative summary.

RULES:
1. Be specific — cite the actual behavioral patterns observed
2. Be actionable — focus on what the manager/rep should do next
3. Be balanced — acknowledge both positive signals and concerns
4. Use plain language — avoid jargon

OUTPUT JSON ONLY. Follow the schema exactly."""

    user_prompt = f"""
Call Analysis Summary Request
===========================

Framework Insights ({len(insights)} top insights):
{insights_text if insights_text else "No insights generated."}

Overall Sentiment Trajectory: {overall_sentiment}
Severity Breakdown: red={severity_counts.get('red', 0)}, orange={severity_counts.get('orange', 0)}, yellow={severity_counts.get('yellow', 0)}, green={severity_counts.get('green', 0)}

Generate a summary with:
1. A narrative paragraph (2-3 sentences) summarizing the call dynamics
2. Key observations (up to 5 bullet points)
3. One recommended focus area for coaching

Return a single JSON object with the specified schema."""

    provider = GeminiProvider()
    llm_config = LLMConfig(
        model=config.llm_pass1.model,
        temperature=0.3,  # Lower temperature for more consistent output
        max_tokens=config.llm_pass1.max_tokens,
        provider="gemini",
    )

    try:
        result = await provider.complete_structured(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            response_model=SummaryOutput,
            config=llm_config,
        )

        # Format the LLM output as a narrative
        narrative = result.summary_paragraph
        if result.key_observations:
            narrative += "\n\nKey observations:\n"
            for obs in result.key_observations[:3]:
                narrative += f"• {obs}\n"
        if result.recommended_focus:
            narrative += f"\nCoaching focus: {result.recommended_focus}"

        return narrative
    except Exception:
        # If LLM call fails, raise to trigger fallback
        raise


def _generate_fallback_summary(
    verified_insights: list,
    top_insights: list,
    severity_counts: dict,
) -> str:
    """Generate a template-based summary when LLM is unavailable."""
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
            parts.append(f"Primary coaching opportunity: {reco}...")

    return " ".join(parts)


def _generate_headline(severity_counts: dict) -> str:
    """Generate a one-line headline based on severity distribution."""
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

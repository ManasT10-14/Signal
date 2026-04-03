"""
Pass 1 extraction node — runs the infrastructure LLM call once per call.
Extracts hedge map, sentiment trajectory, and evaluative language.
"""
from __future__ import annotations

from signalapp.pipeline.state import PipelineState


async def pass1_extract_node(state: PipelineState) -> dict:
    """
    Run Pass 1 infrastructure extraction.

    Inputs: call_id, transcript_segments
    Outputs: pass1_result, pass1_gate_signals (derived)

    Uses Gemini with native JSON schema for structured output.
    """
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig
    from signalapp.prompts.pass1.infrastructure_v1 import (
        Pass1Output,
        build_pass1_prompt,
    )
    from signalapp.domain.routing import Pass1GateSignals

    config = get_config()
    provider = GeminiProvider()

    # Format transcript text from segments
    transcript_text = _format_transcript(state["transcript_segments"])

    # Build prompt
    system_prompt, user_prompt = build_pass1_prompt(transcript_text)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # Run LLM call
    llm_config = LLMConfig(
        model=config.llm_pass1.model,
        temperature=config.llm_pass1.temperature,
        max_tokens=config.llm_pass1.max_tokens,
        provider="gemini",
    )

    try:
        result = await provider.complete_structured(
            prompt=full_prompt,
            response_model=Pass1Output,
            config=llm_config,
        )

        # Serialize Pass1Result into state format
        pass1_result = {
            "hedge_data": [
                h.model_dump() for h in result.hedges
            ],
            "sentiment_data": [
                s.model_dump() for s in result.sentiment_trajectory
            ],
            "appraisal_data": [
                a.model_dump() for a in result.evaluative_language
            ],
            "contains_comparison_language": result.contains_comparison_language,
            "contains_dollar_amount": result.contains_dollar_amount,
            "first_number_speaker": result.first_number_speaker,
            "transcript_duration_minutes": result.transcript_duration_minutes,
            "hedge_density_buyer": result.hedge_density_buyer,
            "hedge_density_rep": result.hedge_density_rep,
            "prompt_version": "v1",
            "model_used": "gemini",
            "model_version": config.llm_pass1.model,
        }

        # Derive Pass1GateSignals from Pass 1 output
        signals = Pass1GateSignals(
            has_competitor_mention=result.contains_comparison_language,
            has_pricing_discussion=result.contains_dollar_amount,
            has_numeric_anchor=result.first_number_speaker is not None,
            has_objection_markers=_detect_objections(result.evaluative_language),
            has_rep_questions=_detect_rep_questions(state["transcript_segments"]),
            has_close_language=_detect_close_language(state["transcript_segments"]),
            call_duration_minutes=result.transcript_duration_minutes,
        )

        return {
            "pass1_result": pass1_result,
            "pass1_gate_signals": signals.__dict__,
        }

    except Exception as e:
        return {
            "pass1_result": None,
            "errors": [f"Pass1 extraction failed: {str(e)}"],
        }


def _format_transcript(segments: list[dict]) -> str:
    """Format serialized TranscriptSegment dicts into LLM input."""
    lines = []
    for seg in segments:
        start_ms = seg.get("start_time_ms", 0)
        mins, secs = divmod(start_ms // 1000, 60)
        timestamp = f"{mins:02d}:{secs:02d}"
        speaker = seg.get("speaker_name", "Unknown")
        role = seg.get("speaker_role", "unknown")
        text = seg.get("text", "")
        lines.append(f"[{timestamp}] {speaker} ({role}): {text}")
    return "\n".join(lines)


def _detect_objections(appraisal_data: list) -> bool:
    """Detect objection markers from evaluative language."""
    objection_keywords = {"frustrat", "concern", "issue", "problem", "worry", "difficult", "can't", "won't"}
    for appraisal in appraisal_data:
        # Support both Pydantic models and dicts
        if hasattr(appraisal, "text_excerpt"):
            text = appraisal.text_excerpt.lower()
            polarity = appraisal.polarity
        else:
            text = appraisal.get("text_excerpt", "").lower()
            polarity = appraisal.get("polarity", "")
        if polarity in ("negative", "strongly_negative"):
            if any(kw in text for kw in objection_keywords):
                return True
    return False


def _detect_rep_questions(segments: list[dict]) -> bool:
    """Detect if rep asked 3+ questions (for routing gate).

    Per routing architecture spec: Framework #5 (Question Quality) should
    be skipped if rep asked fewer than 3 questions.
    """
    count = 0
    for seg in segments:
        if seg.get("speaker_role") == "rep":
            text = seg.get("text", "")
            count += text.count("?")
    return count >= 3


def _detect_close_language(segments: list[dict]) -> bool:
    """Detect close/commitment language from buyer.

    Expanded keyword set to catch more close signals including:
    - Direct commitment phrases
    - Forward-looking statements indicating deal intent
    - Positive next-step language
    """
    close_keywords = {
        # Direct commitment
        "move forward", "proceed", "sign", "agree", "commit",
        "go ahead", "let's do it", "sounds good", "deal",
        # Forward intent
        "next step", "next steps", "going forward", "moving forward",
        "move ahead", "go with", "go with that",
        # Positive close signals
        "interested", "ready to", "want to move", "let's schedule",
        "pencil us in", "block time", "put it on the calendar",
        # Budget/authority signals
        "approved", "budget is there", "we have the budget", "can make it happen",
    }
    for seg in segments:
        if seg.get("speaker_role") == "buyer":
            text = seg.get("text", "").lower()
            if any(kw in text for kw in close_keywords):
                return True
    return False

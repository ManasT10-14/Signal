"""
Segment-level coaching node — generates per-segment coaching annotations.

Reads the full transcript sequentially (context-aware) and produces:
- REP segments: "what to say instead" coaching with word-for-word alternatives
- BUYER segments: signal detection ("resistance detected — probing opportunity")
- Clean segments: skipped (no annotation)

Runs AFTER generate_insights so it has framework results as context.
"""
from __future__ import annotations

import json
import logging
import os

from pydantic import BaseModel, Field
from typing import Optional
from signalapp.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


class SegmentAnnotation(BaseModel):
    segment_index: int
    speaker_role: str  # "rep" or "buyer"
    type: str  # "coaching" or "signal"
    what_was_said: str = ""
    what_to_say_instead: str = ""
    why: str = ""
    signal_detected: str = ""
    missed_opportunity: str = ""
    framework_source: str = ""
    severity: str = "yellow"


class SegmentCoachingOutput(BaseModel):
    annotations: list[SegmentAnnotation] = Field(default_factory=list)
    total_coaching_moments: int = 0
    total_signal_moments: int = 0
    overall_assessment: str = ""


SYSTEM_PROMPT = """You are a world-class sales coach reviewing a call transcript SEGMENT BY SEGMENT.

Your job: for each segment that has a coaching opportunity, tell the rep EXACTLY what they should have said instead and WHY, considering the FULL conversation context up to that point.

CRITICAL RULES:
1. CONTEXT-AWARE: When coaching segment N, you MUST consider what was said in segments 1 through N-1. The conversation is sequential — what the rep should say at segment 5 depends on what happened in segments 1-4.
2. ONLY annotate segments with genuine coaching opportunities. Most segments are fine — skip them.
3. For REP segments: provide "what_to_say_instead" — a word-for-word alternative the rep could use next time.
4. For BUYER segments: detect signals the rep should have read (resistance, hesitation, buying signals, emotional shifts) and state what the rep's NEXT response should have been.
5. Keep coaching SHORT (2-3 sentences max per segment). Be direct and actionable.
6. Connect your coaching to the framework insights provided below — reference which framework identified the issue.

ANNOTATION TYPES:
- type="coaching" → for REP segments where the rep said something suboptimal
- type="signal" → for BUYER segments where the buyer revealed something the rep should act on

SEVERITY:
- "red" → Critical miss — this moment likely cost the deal
- "orange" → Important coaching opportunity — deal could improve significantly
- "yellow" → Minor improvement opportunity

SKIP segments that are:
- Greetings, pleasantries, logistics ("Thanks for joining", "Talk soon")
- Segments where the rep performed well (don't annotate good behavior)
- Buyer segments with no notable signal

CONTEXT-AWARE COACHING EXAMPLES:

Example 1 — Segment 3 depends on segments 1-2:
  [Seg 1] Rep: "What are you using now?" (Situation — good)
  [Seg 2] Buyer: "We use System X. It's been okay." (Vague answer)
  [Seg 3] Rep: "Great. So let me tell you about our product." ← COACHING MOMENT

  Coaching for Seg 3: The buyer said "okay" (vague) in segment 2. Instead of pitching, probe: "When you say okay, what would you change if you could?" This surfaces pain the buyer hasn't articulated yet.

Example 2 — Buyer signal at segment 4 depends on conversation flow:
  [Seg 1] Rep: "Our price is $42,000."
  [Seg 2] Buyer: "That's higher than we expected."
  [Seg 3] Rep: "I can do $38,000." ← COACHING (offered discount without probing)
  [Seg 4] Buyer: "Let me think about it." ← SIGNAL (stall because no value established)

  Coaching for Seg 3: Before discounting, you should have asked "What were you expecting, and what's that based on?" The discount at seg 3 came without understanding the buyer's budget rationale — you left money on the table.
  Signal for Seg 4: "Let me think about it" is a stall, not a commitment. This happened because the rep discounted without establishing value. The buyer has no internal reason to say yes.

OUTPUT JSON ONLY."""


USER_PROMPT = """
<call_type>{call_type}</call_type>

<transcript>
{transcript_text}
</transcript>

<framework_insights>
{insights_text}
</framework_insights>

Review this {call_type} call transcript segment by segment. For each segment, consider the FULL conversation context up to that point.

Rules:
1. Read segments in order (1, 2, 3...). When evaluating segment N, consider what happened in segments 1 through N-1.
2. For REP segments with coaching opportunities: provide what_to_say_instead (word-for-word) and why (connected to framework insights).
3. For BUYER segments with signals: describe what the signal means and what the rep should do next.
4. SKIP segments that are fine — only annotate genuine coaching moments.
5. Keep annotations short and actionable.
6. Reference which framework insight supports your coaching (e.g., "NEPQ Methodology Analysis", "Commitment Quality").

Return a JSON object with the specified schema.

Remember: not every segment needs annotation. A good call might have only 2-3 coaching moments. A poor call might have 6-8. Do not force annotations where none are needed."""


async def segment_coaching_node(state: PipelineState) -> dict:
    """Generate context-aware, per-segment coaching annotations."""
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig

    transcript_segments = state.get("transcript_segments", [])
    verified_insights = state.get("verified_insights", [])
    call_type = state.get("call_type", "other")

    if not transcript_segments:
        return {"segment_coaching": None}

    # Check LLM availability
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not (gemini_key or gcp_project):
        logger.warning("[segment_coaching] No LLM credentials — skipping")
        return {"segment_coaching": None}

    config = get_config()

    # Format transcript with segment indices
    transcript_lines = []
    for seg in transcript_segments:
        idx = seg.get("segment_index", 0)
        start_ms = seg.get("start_time_ms", 0)
        m, s = divmod(start_ms // 1000, 60)
        speaker = seg.get("speaker_name", "Unknown")
        role = seg.get("speaker_role", "unknown")
        text = seg.get("text", "")
        transcript_lines.append(f"[Segment {idx}] [{m:02d}:{s:02d}] {speaker} ({role}): {text}")
    transcript_text = "\n".join(transcript_lines)

    # Format top insights for context
    insights_lines = []
    for ins in sorted(verified_insights, key=lambda x: x.get("priority_rank", 99))[:8]:
        sev = ins.get("severity", "green").upper()
        fw = ins.get("framework_name", "")
        headline = ins.get("headline", "")
        coaching = ins.get("coaching_recommendation", "")[:200]
        insights_lines.append(f"[{sev}] {fw}: {headline}\n  Coaching: {coaching}")
    insights_text = "\n\n".join(insights_lines) if insights_lines else "No framework insights available."

    # Build prompt
    formatted_user = USER_PROMPT.format(
        call_type=call_type,
        transcript_text=transcript_text,
        insights_text=insights_text,
    )
    full_prompt = f"{SYSTEM_PROMPT}\n\n{formatted_user}"

    # Call LLM
    provider = GeminiProvider()
    llm_config = LLMConfig(
        model=config.llm_pass1.model,
        temperature=0.15,
        max_tokens=config.llm_pass1.max_tokens,
        provider="gemini",
    )

    try:
        result = await provider.complete_structured(
            prompt=full_prompt,
            response_model=SegmentCoachingOutput,
            config=llm_config,
        )

        coaching_dict = {
            "annotations": [a.model_dump() for a in result.annotations],
            "total_coaching_moments": result.total_coaching_moments,
            "total_signal_moments": result.total_signal_moments,
            "overall_assessment": result.overall_assessment,
        }

        logger.info(f"[segment_coaching] Generated {len(result.annotations)} annotations "
                     f"({result.total_coaching_moments} coaching, {result.total_signal_moments} signals)")

        return {"segment_coaching": coaching_dict}

    except Exception as e:
        logger.warning(f"[segment_coaching] Failed: {e}")
        return {"segment_coaching": None}

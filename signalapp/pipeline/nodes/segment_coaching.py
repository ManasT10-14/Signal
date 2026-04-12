"""
Segment-level deep coaching node — the play-by-play coach.

Transforms Signal from a report card into a PLAY-BY-PLAY COACHING TOOL.
Every coaching moment tells the rep: what happened, what to do instead,
WHY it matters to the deal, and what the buyer was actually thinking.

Runs AFTER generate_insights so it has framework results as context.

Annotation types:
- "coaching"  — Rep said something suboptimal. Word-for-word alternative provided.
- "signal"    — Buyer revealed something the rep should act on.
- "win"       — Rep did something GREAT. Positive reinforcement with explanation.
- "turning_point" — THE critical moment that shaped the deal outcome.
"""
from __future__ import annotations

import json
import logging
import os

from pydantic import BaseModel, Field
from typing import Optional
from signalapp.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


# ── Output Models ─────────────────────────────────────────────────────────────

class AlternativeExchangeTurn(BaseModel):
    """One turn in an alternative dialogue script."""
    speaker: str  # "Rep" or "Buyer"
    text: str


class SegmentAnnotation(BaseModel):
    segment_index: int
    speaker_role: str  # "rep" or "buyer"
    type: str  # "coaching" | "signal" | "win" | "turning_point"

    # --- Core coaching (for type=coaching/turning_point) ---
    what_was_said: str = ""
    what_to_say_instead: str = ""
    why: str = ""

    # --- Alternative exchange: a 2-4 turn mini-script showing ideal flow ---
    alternative_exchange: list[AlternativeExchangeTurn] = Field(default_factory=list)

    # --- Buyer psychology (for type=signal) ---
    signal_detected: str = ""
    missed_opportunity: str = ""
    buyer_thinking: str = ""  # What the buyer was ACTUALLY thinking

    # --- Win celebration (for type=win) ---
    what_was_great: str = ""
    why_it_worked: str = ""

    # --- Deal impact ---
    deal_impact_score: int = 5  # 1-10: how much this moment affected the deal
    deal_impact_explanation: str = ""  # One sentence: "This moment cost you the discovery"

    # --- Conversation dynamics ---
    momentum: str = "neutral"  # "gaining" | "losing" | "neutral"
    coaching_category: str = ""  # questioning | objection_handling | rapport | closing | value_selling | pacing | active_listening | commitment

    # --- Connections ---
    framework_source: str = ""
    related_segments: list[int] = Field(default_factory=list)  # Other segments this connects to
    severity: str = "yellow"  # red | orange | yellow | green (green = win)


class SegmentCoachingOutput(BaseModel):
    annotations: list[SegmentAnnotation] = Field(default_factory=list)
    total_coaching_moments: int = 0
    total_signal_moments: int = 0
    total_wins: int = 0
    turning_point_segment: int = -1  # Index of the most critical moment (-1 = none)
    overall_assessment: str = ""
    conversation_arc: str = ""  # 1-2 sentence description of conversation momentum pattern
    rep_grade: str = ""  # A/B/C/D/F — overall rep performance grade
    strongest_skill: str = ""  # What the rep does best
    biggest_growth_area: str = ""  # #1 area to improve


SYSTEM_PROMPT = """You are the most elite sales coach in the world. You've coached 10,000+ reps and have a gift for spotting the EXACT moment a deal turns — and knowing EXACTLY what the rep should have said instead.

You're reviewing a sales call transcript SEGMENT BY SEGMENT. Your coaching must be so specific and insightful that the rep reads it and thinks: "Holy shit, that's exactly what I should have said."

## YOUR COACHING PHILOSOPHY

1. **THE TURNING POINT**: Every call has ONE moment that matters most. Find it. Mark it as type="turning_point". This is the moment the deal started winning or losing — the hinge of the conversation. There should be exactly ONE turning point per call.

2. **CELEBRATE WINS**: Reps who only hear criticism burn out. When the rep does something GREAT — a perfect question, a masterful reframe, a well-timed pause — mark it as type="win" with severity="green". A great call might have 3-4 wins. Even a bad call should have at least 1 win. Make the rep feel what they did right so they can REPEAT it.

3. **BUYER PSYCHOLOGY DECODER**: For every buyer segment you annotate, tell the rep what the buyer was ACTUALLY thinking beneath the surface. Buyers rarely say what they mean. "Let me think about it" means "You haven't given me a reason to say yes." "That's interesting" means "I'm not interested yet." Decode this.

4. **ALTERNATIVE EXCHANGES**: Don't just say "try this instead." Write out a 2-4 turn mini-dialogue showing EXACTLY how the ideal exchange would have played out. The rep should be able to read this like a script and rehearse it.

5. **DEAL IMPACT**: Score every annotated moment 1-10 for deal impact. A 10 means "this moment alone could win/lose the deal." A 1 means "nice to improve but didn't affect outcome." This helps reps prioritize what to fix first.

6. **MOMENTUM TRACKING**: Track whether the conversation is gaining or losing momentum at each annotated segment. "gaining" means buyer is leaning in, engaging more, showing interest. "losing" means buyer is pulling back, going quiet, getting defensive.

7. **SEQUENTIAL CONTEXT**: When coaching segment N, you MUST consider the FULL conversation from segments 1 through N-1. What the rep should say at segment 8 depends entirely on what happened in segments 1-7. A pitch at segment 3 is bad if the rep hasn't uncovered pain. The same pitch at segment 8 after deep discovery might be perfect.

8. **CONNECTED MOMENTS**: Many coaching moments are linked. If the rep missed a question at segment 3, and the buyer stalled at segment 7, connect them: related_segments=[3] on segment 7's annotation. This shows cause-and-effect.

## ANNOTATION TYPES

### type="coaching" (Rep segments where something could be better)
- `what_was_said`: Quote the key phrase the rep used
- `what_to_say_instead`: Word-for-word alternative (THIS IS THE KILLER FEATURE)
- `why`: 1-2 sentences connecting to framework analysis
- `alternative_exchange`: 2-4 turn script showing the ideal dialogue flow
- `coaching_category`: One of: questioning, objection_handling, rapport, closing, value_selling, pacing, active_listening, commitment
- `deal_impact_score`: 1-10
- `deal_impact_explanation`: One punchy sentence about impact

### type="signal" (Buyer segments revealing something actionable)
- `signal_detected`: What signal the buyer just gave
- `missed_opportunity`: What the rep should have done NEXT
- `buyer_thinking`: What the buyer was ACTUALLY thinking (decode subtext)
- `alternative_exchange`: What the next 2-3 turns should have looked like
- `deal_impact_score`: 1-10
- `coaching_category`: The skill category this relates to

### type="win" (Rep or buyer segments showing excellent execution)
- `what_was_great`: What the rep did brilliantly
- `why_it_worked`: WHY this was effective (behavioral science explanation)
- `deal_impact_score`: 1-10 (high = this win significantly helped the deal)
- severity MUST be "green" for wins

### type="turning_point" (THE most critical moment — exactly ONE per call)
- Same fields as "coaching" or "signal" depending on who's speaking
- `deal_impact_score`: Should be 8-10
- `deal_impact_explanation`: "This was THE moment that..." — make it clear why

## SEVERITY GUIDE
- "red" → Critical miss — this moment likely cost the deal (deal_impact 8-10)
- "orange" → Significant coaching opportunity (deal_impact 5-7)
- "yellow" → Minor improvement (deal_impact 2-4)
- "green" → ONLY for type="win" — rep did great (deal_impact varies)

## MOMENTUM VALUES
- "gaining" → Buyer is leaning in, asking questions, sharing information
- "losing" → Buyer is pulling back, giving short answers, showing resistance
- "neutral" → No significant shift

## COACHING CATEGORIES
- questioning → Quality and timing of questions
- objection_handling → Handling buyer pushback
- rapport → Building connection and trust
- closing → Moving toward commitment
- value_selling → Communicating value proposition
- pacing → Conversation speed and timing
- active_listening → Picking up on buyer cues
- commitment → Securing next steps

## QUALITY RULES
1. Annotate 25-40% of segments (not too few, not too many)
2. At least 1-2 wins even in a bad call (positive reinforcement)
3. Exactly 1 turning point per call
4. Alternative exchanges must feel natural — like real dialogue, not textbook
5. buyer_thinking should be insightful, not obvious
6. Connect related moments with related_segments
7. Overall assessment should be 2-3 sentences: honest but encouraging
8. Give a letter grade (A/B/C/D/F) and identify strongest skill + biggest growth area
9. Keep individual annotations concise but impactful
10. conversation_arc should describe the momentum pattern (e.g., "Strong opening that lost steam after pricing — buyer disengaged when rep couldn't justify ROI")

## WHAT TO SKIP
- Greetings, pleasantries, logistics — never annotate these
- Segments where the rep performed adequately (not great, not bad)
- Buyer segments with no notable signal
- Repetitive coaching — if you've already coached on questioning technique, don't repeat it on every question

OUTPUT JSON ONLY."""


USER_PROMPT = """
<call_type>{call_type}</call_type>

<transcript>
{transcript_text}
</transcript>

<framework_insights>
{insights_text}
</framework_insights>

<base_metrics>
{metrics_text}
</base_metrics>

Coach this {call_type} call. Read every segment sequentially, considering the FULL conversation context at each point.

Your output MUST include:
1. Annotations for 25-40% of segments (mix of coaching, signal, win, and exactly one turning_point)
2. At least 1-2 wins (type="win", severity="green") — celebrate what the rep did right
3. Exactly ONE turning_point — THE most critical moment
4. buyer_thinking for every buyer signal annotation
5. alternative_exchange scripts (2-4 turns) for coaching and turning_point annotations
6. deal_impact_score (1-10) for every annotation
7. connected related_segments where coaching moments are linked
8. overall_assessment (2-3 sentences), rep_grade (A-F), strongest_skill, biggest_growth_area
9. conversation_arc describing the momentum pattern

Return a JSON object matching the schema exactly."""


async def segment_coaching_node(state: PipelineState) -> dict:
    """Generate rich, context-aware, per-segment coaching annotations."""
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig

    transcript_segments = state.get("transcript_segments", [])
    verified_insights = state.get("verified_insights", [])
    call_type = state.get("call_type", "other")
    base_metrics = state.get("base_metrics") or {}

    if not transcript_segments:
        return {"segment_coaching": None}

    # Check LLM availability
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not (gemini_key or gcp_project):
        logger.warning("[segment_coaching] No LLM credentials — skipping")
        return {"segment_coaching": None}

    config = get_config()

    # Format transcript with segment indices and roles
    transcript_lines = []
    for seg in transcript_segments:
        idx = seg.get("segment_index", 0)
        start_ms = seg.get("start_time_ms", 0)
        m, s = divmod(start_ms // 1000, 60)
        speaker = seg.get("speaker_name", "Unknown")
        role = seg.get("speaker_role", "unknown")
        text = seg.get("text", "")
        word_count = len(text.split())
        transcript_lines.append(
            f"[Segment {idx}] [{m:02d}:{s:02d}] {speaker} ({role}) [{word_count}w]: {text}"
        )
    transcript_text = "\n".join(transcript_lines)

    # Format top insights for context — give the LLM rich framework data
    insights_lines = []
    for ins in sorted(verified_insights, key=lambda x: x.get("priority_rank", 99))[:10]:
        sev = ins.get("severity", "green").upper()
        fw = ins.get("framework_name", "")
        headline = ins.get("headline", "")
        explanation = ins.get("explanation", "")[:300]
        coaching = ins.get("coaching_recommendation", "")[:300]
        evidence = ins.get("evidence", [])
        ev_text = ""
        for ev in evidence[:3]:
            q = ev.get("quote", "")
            seg_idx = ev.get("segment_index", "?")
            if q:
                ev_text += f'\n    Evidence (seg {seg_idx}): "{q[:120]}"'
        insights_lines.append(
            f"[{sev}] {fw}: {headline}\n  Detail: {explanation}\n  Coaching: {coaching}{ev_text}"
        )
    insights_text = "\n\n".join(insights_lines) if insights_lines else "No framework insights available."

    # Format base metrics for context
    metrics_lines = []
    if base_metrics:
        rep_talk = base_metrics.get("rep_talk_ratio", 0)
        buyer_talk = base_metrics.get("buyer_talk_ratio", 0)
        rep_q = base_metrics.get("rep_questions", 0)
        buyer_q = base_metrics.get("buyer_questions", 0)
        interrupts = base_metrics.get("interruption_count", 0)
        rep_wpm = base_metrics.get("rep_wpm", 0)
        metrics_lines = [
            f"Talk ratio: Rep {rep_talk:.0%} / Buyer {buyer_talk:.0%}",
            f"Questions: Rep asked {rep_q}, Buyer asked {buyer_q}",
            f"Rep WPM: {rep_wpm}",
            f"Interruptions: {interrupts}",
        ]
    metrics_text = "\n".join(metrics_lines) if metrics_lines else "No base metrics available."

    # Build prompt
    formatted_user = USER_PROMPT.format(
        call_type=call_type,
        transcript_text=transcript_text,
        insights_text=insights_text,
        metrics_text=metrics_text,
    )
    full_prompt = f"{SYSTEM_PROMPT}\n\n{formatted_user}"

    # Call LLM — use slightly higher temperature for creative coaching
    provider = GeminiProvider()
    llm_config = LLMConfig(
        model=config.llm_pass1.model,
        temperature=0.20,
        max_tokens=config.llm_pass1.max_tokens,
        provider="gemini",
    )

    try:
        result = await provider.complete_structured(
            prompt=full_prompt,
            response_model=SegmentCoachingOutput,
            config=llm_config,
        )

        # Post-process: ensure exactly one turning point
        turning_points = [a for a in result.annotations if a.type == "turning_point"]
        if len(turning_points) > 1:
            # Keep only the highest deal_impact one
            best_tp = max(turning_points, key=lambda a: a.deal_impact_score)
            for a in turning_points:
                if a.segment_index != best_tp.segment_index:
                    a.type = "coaching"  # Downgrade extras to coaching

        # Ensure wins have green severity
        for a in result.annotations:
            if a.type == "win":
                a.severity = "green"

        # Recount
        coaching_count = sum(1 for a in result.annotations if a.type == "coaching")
        signal_count = sum(1 for a in result.annotations if a.type == "signal")
        win_count = sum(1 for a in result.annotations if a.type == "win")
        tp_seg = next((a.segment_index for a in result.annotations if a.type == "turning_point"), -1)

        coaching_dict = {
            "annotations": [a.model_dump() for a in result.annotations],
            "total_coaching_moments": coaching_count,
            "total_signal_moments": signal_count,
            "total_wins": win_count,
            "turning_point_segment": tp_seg,
            "overall_assessment": result.overall_assessment,
            "conversation_arc": result.conversation_arc,
            "rep_grade": result.rep_grade,
            "strongest_skill": result.strongest_skill,
            "biggest_growth_area": result.biggest_growth_area,
        }

        logger.info(
            f"[segment_coaching] Generated {len(result.annotations)} annotations "
            f"({coaching_count} coaching, {signal_count} signals, {win_count} wins, "
            f"turning_point={tp_seg}) — grade={result.rep_grade}"
        )

        return {"segment_coaching": coaching_dict}

    except Exception as e:
        logger.warning(f"[segment_coaching] Failed: {e}")
        return {"segment_coaching": None}

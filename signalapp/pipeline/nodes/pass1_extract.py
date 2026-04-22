"""
Pass 1 extraction node — runs the infrastructure LLM call once per call.
Extracts hedge map, sentiment trajectory, and evaluative language.
"""
from __future__ import annotations

import os
import re
from signalapp.pipeline.state import PipelineState


def _check_llm_available() -> bool:
    """Check if LLM credentials are configured."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    return bool(gemini_key or gcp_project)


async def pass1_extract_node(state: PipelineState) -> dict:
    """
    Run Pass 1 infrastructure extraction.

    Inputs: call_id, transcript_segments
    Outputs: pass1_result, pass1_gate_signals (derived)

    Uses Gemini with native JSON schema for structured output.
    Fails fast when no LLM is configured.
    """
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig
    from signalapp.prompts.pass1.infrastructure_v1 import (
        Pass1Output,
        build_pass1_prompt,
    )
    from signalapp.domain.routing import Pass1GateSignals

    # LLM availability guard — fail fast if no credentials
    if not _check_llm_available():
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "pass1_extract_node: No LLM credentials configured. "
            "Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT. Returning stub pass1 result."
        )
        # Return stub pass1 result so pipeline continues
        segment_count = len(state.get("transcript_segments", []))
        estimated_duration = segment_count * 30.0  # ~30s per segment
        stub_pass1 = {
            "hedge_data": [],
            "sentiment_data": [],
            "appraisal_data": [],
            "contains_comparison_language": False,
            "contains_dollar_amount": False,
            "first_number_speaker": None,
            "transcript_duration_minutes": estimated_duration / 60.0,
            "hedge_density_buyer": 0.0,
            "hedge_density_rep": 0.0,
            "spin_questions": [],
            "spin_counts": {"S": 0, "P": 0, "I": 0, "N": 0},
            "spin_ratio": 0.0,
            "prompt_version": "stub",
            "model_used": "none",
            "model_version": "stub",
        }
        signals = Pass1GateSignals(
            has_competitor_mention=False,
            has_pricing_discussion=False,
            has_numeric_anchor=False,
            has_objection_markers=False,
            has_rep_questions=_detect_rep_questions(state["transcript_segments"]),
            has_close_language=_detect_close_language(state["transcript_segments"]),
            call_duration_minutes=estimated_duration / 60.0,
        )
        return {
            "pass1_result": stub_pass1,
            "pass1_gate_signals": signals.__dict__,
        }

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

    import logging
    logger = logging.getLogger(__name__)

    # ── Attempt with retry + partial extraction ──────────────────────────────────
    raw_text = None
    for attempt in range(3):
        try:
            result = await provider.complete_structured(
                prompt=full_prompt,
                response_model=Pass1Output,
                config=llm_config,
            )

            # Serialize SPIN questions and compute counts + ratio
            spin_questions_raw = [q.model_dump() for q in getattr(result, "spin_questions", []) or []]
            spin_questions = _normalize_spin_questions(spin_questions_raw)
            if not spin_questions:
                # Fallback: empty from LLM — skip keyword fallback here since LLM is richer;
                # downstream consumers gate on spin_ratio.
                pass
            spin_counts = _compute_spin_counts(spin_questions)
            spin_ratio = _compute_spin_ratio(spin_counts)

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
                "spin_questions": spin_questions,
                "spin_counts": spin_counts,
                "spin_ratio": spin_ratio,
                "prompt_version": "v1",
                "model_used": "gemini",
                "model_version": config.llm_pass1.model,
            }

            # Derive Pass1GateSignals — LLM output enriched with keyword fallbacks
            transcript_segs = state["transcript_segments"]
            signals = Pass1GateSignals(
                has_competitor_mention=result.contains_comparison_language or _detect_competitor_mention(transcript_segs),
                has_pricing_discussion=result.contains_dollar_amount or _detect_pricing_discussion(transcript_segs),
                has_numeric_anchor=(result.first_number_speaker is not None) or _detect_numeric_anchor(transcript_segs),
                has_objection_markers=_detect_objections(result.evaluative_language) or _detect_objection_from_text(transcript_segs),
                has_rep_questions=_detect_rep_questions(transcript_segs),
                has_close_language=_detect_close_language(transcript_segs),
                call_duration_minutes=result.transcript_duration_minutes,
            )

            return {
                "pass1_result": pass1_result,
                "pass1_gate_signals": signals.__dict__,
            }

        except Exception as e:
            error_str = str(e)
            if attempt < 2:
                # Retry with hint to keep output shorter
                full_prompt = full_prompt + (
                    "\n\nIMPORTANT: Keep output JSON very concise — under 2000 tokens total."
                )
                logger.warning(f"pass1_extract_node: attempt {attempt+1} failed: {error_str[:150]}. Retrying with shorter output hint...")
                continue

            # All retries exhausted — try partial extraction from raw response
            if raw_text is None:
                raw_text = _get_raw_response_text(provider, full_prompt, llm_config)

            partial = _try_partial_pass1_extraction(raw_text, state["transcript_segments"])
            if partial is not None:
                logger.warning(f"pass1_extract_node: using partial Pass1 data after {attempt+1} failed attempts.")
                return {
                    "pass1_result": partial,
                    "pass1_gate_signals": _gate_signals_from_pass1(partial, state["transcript_segments"]).__dict__,
                    "errors": [f"Partial Pass1 (retry {attempt+1} failed): {error_str[:100]}"],
                }

            # Complete failure — return stub
            logger.warning(f"pass1_extract_node: all attempts failed: {error_str[:200]}. Using stub signals.")
            segment_count = len(state.get("transcript_segments", []))
            estimated_duration = segment_count * 30.0
            fallback_spin = _classify_spin_keyword(state["transcript_segments"])
            stub_pass1 = {
                "hedge_data": [],
                "sentiment_data": [],
                "appraisal_data": [],
                "contains_comparison_language": False,
                "contains_dollar_amount": False,
                "first_number_speaker": None,
                "transcript_duration_minutes": estimated_duration / 60.0,
                "hedge_density_buyer": 0.0,
                "hedge_density_rep": 0.0,
                "spin_questions": fallback_spin,
                "spin_counts": _compute_spin_counts(fallback_spin),
                "spin_ratio": _compute_spin_ratio(_compute_spin_counts(fallback_spin)),
                "prompt_version": "stub",
                "model_used": "none",
                "model_version": "stub",
            }
            # Use keyword-based fallback detectors for all signals
            transcript_segs = state["transcript_segments"]
            signals = Pass1GateSignals(
                has_competitor_mention=_detect_competitor_mention(transcript_segs),
                has_pricing_discussion=_detect_pricing_discussion(transcript_segs),
                has_numeric_anchor=_detect_numeric_anchor(transcript_segs),
                has_objection_markers=_detect_objection_from_text(transcript_segs),
                has_rep_questions=_detect_rep_questions(transcript_segs),
                has_close_language=_detect_close_language(transcript_segs),
                call_duration_minutes=estimated_duration / 60.0,
            )
            return {
                "pass1_result": stub_pass1,
                "pass1_gate_signals": signals.__dict__,
                "errors": [f"Pass1 extraction failed: {error_str[:200]} — using stub"],
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
    """Detect close/commitment language — phrase-level matching only.

    High precision: only fires on unambiguous deal-closing phrases.
    Generic phrases like 'interested', 'next steps', 'schedule' are excluded
    because they appear in discovery and check-in calls too.
    """
    close_phrases = {
        # Explicit forward motion
        "move forward with", "ready to move forward", "let's move forward",
        "ready to proceed", "let's proceed", "proceed with",
        "move ahead with", "ready to move ahead",
        # Signing / commitment
        "sign the contract", "sign the agreement", "sign off on", "ready to sign",
        "ready to commit", "commit to this", "we're committed",
        "let's do it", "let's go with", "go with that", "go with you",
        # Budget / approval for THIS deal
        "we have the budget", "budget is approved", "budget is there",
        "got approval", "get approval", "get sign-off",
        # Document actions indicating close
        "send the contract", "send over the contract", "draft the agreement",
        "finalize the deal", "finalize the agreement", "finalize the contract",
        "close the deal", "close this out",
        # Direct purchase intent
        "ready to buy", "want to buy", "let's close",
    }
    for seg in segments:
        text = seg.get("text", "").lower()
        if any(phrase in text for phrase in close_phrases):
            return True
    return False


def _detect_competitor_mention(segments: list[dict]) -> bool:
    """Detect competitor or alternative vendor mentions — phrase-level.

    Excludes generic words like 'evaluating', 'alternative', 'currently using'
    which trigger false positives on discovery calls.
    """
    competitor_phrases = {
        # Direct competitor references
        "competitor", "other vendor", "other option", "other solution", "other provider",
        "competing product", "competing solution", "competing vendor",
        # Comparison activity
        "also looking at", "compared to", "versus", "narrowed it down",
        "their pricing", "their product", "they offer", "they quoted",
        # Evaluation of alternatives (specific phrases)
        "evaluating other", "evaluating alternatives",
        "looking at alternatives", "considering alternatives",
        "also talking to", "also working with",
        "shortlisted", "on our shortlist",
        "how do you compare", "how does this compare",
        # Specific switching context
        "switch from", "switch to them", "switching from",
    }
    for seg in segments:
        text = seg.get("text", "").lower()
        if any(phrase in text for phrase in competitor_phrases):
            return True
    return False


def _detect_pricing_discussion(segments: list[dict]) -> bool:
    """Detect active pricing/cost discussions — phrase-level matching.

    Excludes single words like 'rate', 'investment', 'proposal', 'budget'
    which trigger false positives (e.g., 'win rates', 'time investment',
    'is there budget allocated').
    """
    pricing_phrases = {
        # Pricing-specific terms (unambiguous)
        "pricing", "discount", "cheaper", "expensive",
        "per seat", "per user", "per month", "per year", "per license",
        # Pricing discussion context
        "price point", "price range", "your pricing", "our pricing", "the pricing",
        "the cost of", "total cost", "how much does", "how much would",
        "annual cost", "monthly cost", "cost per",
        # Budget in deal context
        "within budget", "over budget", "under budget", "above budget",
        "budget is", "our budget is", "my budget is",
        # Explicit rate context (not 'win rate')
        "rate per", "billing cycle",
        # Dollar negotiation
        "reduction in price", "bring it down", "come down on price",
        "can you do", "what can you do on",
    }
    for seg in segments:
        text = seg.get("text", "").lower()
        if any(phrase in text for phrase in pricing_phrases):
            return True
        # Dollar amounts only (requires $ sign — unambiguous)
        if re.search(r'\$\d[\d,]*', text):
            return True
    return False


def _detect_numeric_anchor(segments: list[dict]) -> bool:
    """Detect if a specific price/number was proposed as a negotiation position.

    Only matches dollar amounts and numbers with explicit pricing context.
    Excludes bare numbers, years, percentages, and counts.
    """
    _ANCHOR_PATTERNS = [
        re.compile(r'\$\d[\d,]*'),                              # $50, $28,000
        re.compile(r'\b\d[\d,]*\s+dollars\b', re.IGNORECASE),   # 500 dollars
        re.compile(r'\b\d[\d,]*\s*(?:per|a|/)\s*(?:seat|user|license|month|year)\b', re.IGNORECASE),
        re.compile(r'\b\d+k\s*(?:per|a|/)\s*(?:seat|user|month|year)\b', re.IGNORECASE),
    ]
    for seg in segments:
        text = seg.get("text", "")
        for pattern in _ANCHOR_PATTERNS:
            if pattern.search(text):
                return True
    return False


def _detect_objection_from_text(segments: list[dict]) -> bool:
    """Detect buyer pushback against the rep's proposal — phrase-level.

    Only checks buyer segments. Excludes generic words like 'concern', 'issue',
    'problem', 'but', 'however' which trigger false positives when buyer
    describes general business problems (not objecting to the rep).
    """
    objection_phrases = {
        # Direct pushback on price/proposal
        "can't justify", "too expensive", "above budget", "higher than expected",
        "not comfortable with", "can't afford", "over our budget",
        "that's too much", "that's a lot", "that seems high", "seems expensive",
        "not in our budget", "exceeds our budget",
        # Resistance / stalling on the rep's offer
        "we can't do that", "i don't think we can", "won't be able to",
        "not going to work", "that doesn't work", "that won't work",
        "need to think about", "need to run this by", "need more time",
        # Structured concern about the offer
        "my concern is", "our concern is", "i have concerns about",
        "the issue with that", "the problem with that",
        "not what we were expecting", "not what i expected",
        "push back", "pushback",
    }
    for seg in segments:
        if seg.get("speaker_role") == "buyer":
            text = seg.get("text", "").lower()
            if any(phrase in text for phrase in objection_phrases):
                return True
    return False


# ── Partial extraction helpers for Pass1 ────────────────────────────────────────

import json


def _get_raw_response_text(provider, prompt: str, llm_config) -> str | None:
    """Get raw text from Vertex AI / Gemini for partial JSON extraction."""
    try:
        client = provider._get_client()
        from google.genai import types as google_types
        gen_config = google_types.GenerateContentConfig(
            temperature=llm_config.temperature,
            max_output_tokens=llm_config.max_tokens,
        )
        response = client.models.generate_content(
            model=llm_config.model,
            contents=prompt,
            config=gen_config,
        )
        return response.text
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"_get_raw_response_text failed: {type(e).__name__}: {e}")
        return None


def _try_partial_pass1_extraction(raw_text: str | None, segments: list[dict]) -> dict | None:
    """Try to extract partial Pass1 fields from raw LLM text when Pydantic validation fails."""
    if not raw_text:
        return None

    # Strip markdown code fences
    text = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
        else:
            return None

    if not isinstance(data, dict):
        return None

    # Try to extract hedge data
    hedges = []
    for h in (data.get("hedges") or [])[:10]:
        if isinstance(h, dict):
            hedges.append({
                "text_excerpt": h.get("text_excerpt", "")[:200],
                "speaker_name": h.get("speaker_name", ""),
                "speaker_role": h.get("speaker_role", "unknown"),
                "start_time_ms": h.get("start_time_ms", 0),
                "end_time_ms": h.get("end_time_ms", 0),
                "hedging_signal": h.get("hedging_signal", "qualifier"),
            })

    # Try to extract sentiment trajectory
    sentiment = []
    for s in (data.get("sentiment_trajectory") or [])[:10]:
        if isinstance(s, dict):
            sentiment.append({
                "speaker_name": s.get("speaker_name", ""),
                "speaker_role": s.get("speaker_role", "unknown"),
                "valence": s.get("valence", "neutral"),
                "intensity": s.get("intensity", 0.5),
                "start_time_ms": s.get("start_time_ms", 0),
                "end_time_ms": s.get("end_time_ms", 0),
            })

    # Try appraisal data
    appraisals = []
    for a in (data.get("evaluative_language") or data.get("appraisal_data") or [])[:10]:
        if isinstance(a, dict):
            appraisals.append({
                "text_excerpt": a.get("text_excerpt", "")[:200],
                "polarity": a.get("polarity", "neutral"),
                "intensity": a.get("intensity", 0.5),
                "speaker_name": a.get("speaker_name", ""),
            })

    # Check we got something meaningful
    if not (hedges or sentiment or appraisals):
        return None

    # Estimate duration from segments
    seg_count = len(segments)
    duration_min = max(seg_count * 0.5, 1.0)

    # Extract booleans
    comp_lang = bool(data.get("contains_comparison_language"))
    dollar = bool(data.get("contains_dollar_amount"))
    first_num = data.get("first_number_speaker")

    # SPIN — prefer LLM output, fall back to keyword classifier if absent
    raw_spin = data.get("spin_questions") or []
    spin_norm = _normalize_spin_questions(raw_spin if isinstance(raw_spin, list) else [])
    if not spin_norm:
        spin_norm = _classify_spin_keyword(segments)
    spin_counts = _compute_spin_counts(spin_norm)

    return {
        "hedge_data": hedges,
        "sentiment_data": sentiment,
        "appraisal_data": appraisals,
        "contains_comparison_language": comp_lang,
        "contains_dollar_amount": dollar,
        "first_number_speaker": first_num,
        "transcript_duration_minutes": data.get("transcript_duration_minutes", duration_min),
        "hedge_density_buyer": data.get("hedge_density_buyer", 0.0),
        "hedge_density_rep": data.get("hedge_density_rep", 0.0),
        "spin_questions": spin_norm,
        "spin_counts": spin_counts,
        "spin_ratio": _compute_spin_ratio(spin_counts),
        "prompt_version": "partial",
        "model_used": "gemini",
        "model_version": "partial",
    }


def _gate_signals_from_pass1(pass1_result: dict, segments: list[dict]) -> "Pass1GateSignals":
    """Derive Pass1GateSignals from partial pass1 result dict."""
    hedge_data = pass1_result.get("hedge_data", [])
    dollar = pass1_result.get("contains_dollar_amount", False)
    comp = pass1_result.get("contains_comparison_language", False)
    first_num = pass1_result.get("first_number_speaker")
    dur = pass1_result.get("transcript_duration_minutes", 1.0)

    # Detect objections from appraisal data
    appraisal = pass1_result.get("appraisal_data", [])
    objection_markers = any(
        kw in str(a.get("text_excerpt", "")).lower()
        for a in appraisal
        for kw in ("frustrat", "concern", "issue", "problem", "worry")
        if a.get("polarity") in ("negative", "strongly_negative")
    )

    # Use keyword fallbacks to enrich signals beyond what LLM extracted
    return Pass1GateSignals(
        has_competitor_mention=comp or _detect_competitor_mention(segments),
        has_pricing_discussion=dollar or _detect_pricing_discussion(segments),
        has_numeric_anchor=(first_num is not None) or _detect_numeric_anchor(segments),
        has_objection_markers=objection_markers or _detect_objection_from_text(segments),
        has_rep_questions=_detect_rep_questions(segments),
        has_close_language=_detect_close_language(segments),
        call_duration_minutes=dur,
    )


# ── SPIN classification helpers ─────────────────────────────────────────────────

_VALID_SPIN = {"S", "P", "I", "N"}


def _normalize_spin_questions(raw: list) -> list[dict]:
    """Normalize LLM-provided SPIN instances into our canonical dict shape.

    Drops anything that isn't a dict with a valid spin_type.
    """
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:30]:  # hard cap to prevent runaway LLM output
        if not isinstance(item, dict):
            continue
        stype = str(item.get("spin_type", "")).strip().upper()
        if stype not in _VALID_SPIN:
            continue
        text = str(item.get("text_excerpt", "")).strip()
        if not text:
            continue
        out.append({
            "segment_id": str(item.get("segment_id", "") or ""),
            "speaker_role": str(item.get("speaker_role", "rep") or "rep"),
            "spin_type": stype,
            "text_excerpt": text[:300],
        })
    return out


def _compute_spin_counts(spin_questions: list[dict]) -> dict:
    counts = {"S": 0, "P": 0, "I": 0, "N": 0}
    for q in spin_questions:
        t = q.get("spin_type")
        if t in counts:
            counts[t] += 1
    return counts


def _compute_spin_ratio(counts: dict) -> float:
    """Rackham's insight: top reps invert the S+P vs I+N ratio.

    Returns (I + N) / max(1, S + P). 1.0 = balanced, >1.0 = implication/payoff heavy.
    """
    sp = counts.get("S", 0) + counts.get("P", 0)
    in_ = counts.get("I", 0) + counts.get("N", 0)
    return round(in_ / max(1, sp), 3)


# Keyword/heuristic fallback classifier — used when LLM fails or in stub paths.
# Precision over recall: we'd rather mark "unclassified" than mis-label a Situation question as Implication.
_IMPLICATION_MARKERS = (
    "what happens if", "what happens when", "how does that affect", "how does that impact",
    "what's the impact", "what is the impact", "cost you", "costing you",
    "consequence", "consequences", "downstream", "ripple effect",
    "if that continues", "if that persists", "if nothing changes",
)
_NEED_PAYOFF_MARKERS = (
    "how valuable", "how useful", "what would it mean", "what would that mean",
    "how would that help", "what would you do with", "how much would you save",
    "what would you save", "if we could", "if we solved", "if you could",
    "how important is it to", "how critical",
)
_PROBLEM_MARKERS = (
    "what's frustrating", "what is frustrating", "what's the biggest challenge",
    "biggest challenge", "biggest pain", "falling short", "not working",
    "what's not working", "what isn't working", "where are you stuck",
    "what's holding", "what's blocking", "what goes wrong", "what keeps you up",
    "pain point", "what concerns", "difficulties", "struggling with",
)
_SITUATION_MARKERS = (
    "how many", "how long", "how often", "what tool", "which tool",
    "what system", "which system", "who", "when did", "where do you",
    "walk me through", "tell me about your current", "describe your current",
    "what does your", "what do you currently",
)


def _classify_spin_keyword(segments: list[dict]) -> list[dict]:
    """Best-effort SPIN classification from rep questions using keyword markers.

    Only fires when the LLM path failed. Returns the canonical dict shape.
    """
    out: list[dict] = []
    for seg in segments:
        if seg.get("speaker_role") != "rep":
            continue
        text = str(seg.get("text", "") or "")
        if "?" not in text:
            continue
        # Split by sentences so we classify per-question, not per-segment
        for sentence in re.split(r'(?<=[.?!])\s+', text):
            if "?" not in sentence:
                continue
            q = sentence.strip()
            if len(q) < 6:
                continue
            low = q.lower()
            stype = None
            if any(m in low for m in _IMPLICATION_MARKERS):
                stype = "I"
            elif any(m in low for m in _NEED_PAYOFF_MARKERS):
                stype = "N"
            elif any(m in low for m in _PROBLEM_MARKERS):
                stype = "P"
            elif any(m in low for m in _SITUATION_MARKERS):
                stype = "S"
            if stype is None:
                continue
            out.append({
                "segment_id": str(seg.get("segment_id", "") or ""),
                "speaker_role": "rep",
                "spin_type": stype,
                "text_excerpt": q[:300],
            })
            if len(out) >= 20:
                return out
    return out

"""
Framework group execution node — fans out to Pass 2 group LLM calls in parallel.

Each group (A/B/C/E) runs concurrently. Within each group, frameworks run concurrently.
All results are collected into framework_results dict keyed by fw_id.
"""
from __future__ import annotations

import asyncio
import logging
import os
from signalapp.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

# Mapping: fw_id (int) → (group_id, prompt_module_path, output_class_name)
# prompt_module_path: dotted path to the module
# output_class_name: Pydantic output model class name
FW_PROMPT_MAP: dict[int, tuple[str, str, str]] = {
    # Group A — Negotiation Intelligence
    3: ("A", "signalapp.prompts.groups.group_a.batna_detection_v1", "BatnaDetectionOutput"),
    4: ("A", "signalapp.prompts.groups.group_a.money_left_on_table_v1", "MoneyLeftOnTableOutput"),
    7: ("A", "signalapp.prompts.groups.group_a.first_number_tracker_v1", "FirstNumberTrackerOutput"),
    12: ("A", "signalapp.prompts.groups.group_a.deal_health_v1", "DealHealthOutput"),
    13: ("A", "signalapp.prompts.groups.group_a.deal_timing_v1", "DealTimingOutput"),
    # Group B — Pragmatic Intelligence
    1: ("B", "signalapp.prompts.groups.group_b.unanswered_questions_v1", "UnansweredQuestionsOutput"),
    2: ("B", "signalapp.prompts.groups.group_b.commitment_quality_v1", "CommitmentQualityOutput"),
    6: ("B", "signalapp.prompts.groups.group_b.commitment_thermometer_v1", "CommitmentThermometerOutput"),
    16: ("B", "signalapp.prompts.groups.group_b.pushback_classification_v1", "PushbackClassificationOutput"),
    # Group C — Strategic Clarity
    5: ("C", "signalapp.prompts.groups.group_c.question_quality_v1", "QuestionQualityOutput"),
    10: ("C", "signalapp.prompts.groups.group_c.frame_match_v1", "FrameMatchOutput"),
    11: ("C", "signalapp.prompts.groups.group_c.close_attempt_v1", "CloseAttemptOutput"),
    14: ("C", "signalapp.prompts.groups.group_c.methodology_v1", "MethodologyComplianceOutput"),
    15: ("C", "signalapp.prompts.groups.group_c.call_structure_v1", "CallStructureOutput"),
    17: ("C", "signalapp.prompts.groups.group_c.objection_response_v1", "ObjectionResponseOutput"),
    # Group E — Emotional Resonance
    8: ("E", "signalapp.prompts.groups.group_e.emotional_turning_points_v1", "EmotionTriggerOutput"),
    9: ("E", "signalapp.prompts.groups.group_e.emotional_turning_points_v1", "EmotionTriggerOutput"),
    # Group F — NEPQ Methodology Intelligence
    20: ("F", "signalapp.prompts.groups.group_f.nepq_analysis_v1", "NEPQAnalysisOutput"),
}


# Group → LLM config key in AppConfig
GROUP_LLM_CONFIG_KEY: dict[str, str] = {
    "A": "llm_group_a",
    "B": "llm_group_b",
    "C": "llm_group_c",
    "E": "llm_group_e",
    "F": "llm_group_f",
}


def _check_llm_available() -> bool:
    """Check if LLM credentials are configured."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    return bool(gemini_key or gcp_project)


async def execute_groups_node(state: PipelineState) -> dict:
    """
    Execute all active framework groups in parallel.

    Inputs: active_frameworks, pass1_result, transcript_segments
    Outputs: framework_results (fw_id → FrameworkOutput), framework_errors (fw_id → error str)

    Fails gracefully: individual framework errors don't block other frameworks.
    """
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig
    from signalapp.domain.framework import FrameworkOutput

    # LLM availability guard — fail fast if no credentials
    if not _check_llm_available():
        logger.warning(
            "execute_groups_node: No LLM credentials configured. "
            "Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT environment variable. "
            "Returning stub results."
        )
        active_frameworks = state.get("active_frameworks", [])
        framework_results = {}
        framework_errors = {}
        for fw_id in active_frameworks:
            framework_results[fw_id] = _stub_framework_output(
                fw_id, "LLM credentials not configured"
            ).model_dump()
            framework_errors[fw_id] = "LLM not available"
        return {
            "framework_results": framework_results,
            "framework_errors": framework_errors,
        }

    config = get_config()
    provider = GeminiProvider()

    active_frameworks = state["active_frameworks"]
    pass1_result = state.get("pass1_result") or {}

    if not active_frameworks:
        return {"framework_results": {}, "framework_errors": {}}

    # Format transcript for prompts
    transcript_text = _format_transcript(state["transcript_segments"])
    call_type = state.get("call_type", "other")
    hedge_data = pass1_result.get("hedge_data", [])
    sentiment_data = pass1_result.get("sentiment_data", [])
    appraisal_data = pass1_result.get("appraisal_data", [])

    # Build tasks for all active frameworks
    tasks = []
    fw_ids = sorted(active_frameworks)

    for fw_id in fw_ids:
        if fw_id not in FW_PROMPT_MAP:
            # Unknown framework — skip gracefully
            continue

        group_id, module_path, output_class_name = FW_PROMPT_MAP[fw_id]

        # Get LLM config for this group
        config_key = GROUP_LLM_CONFIG_KEY.get(group_id, "llm_group_b")
        llm_config_obj = getattr(config, config_key, config.llm_group_b)

        task = _run_framework(
            provider=provider,
            fw_id=fw_id,
            group_id=group_id,
            module_path=module_path,
            output_class_name=output_class_name,
            llm_config=LLMConfig(
                model=llm_config_obj.model,
                temperature=llm_config_obj.temperature,
                max_tokens=llm_config_obj.max_tokens,
                provider="gemini",
            ),
            transcript_text=transcript_text,
            call_type=call_type,
            hedge_data=hedge_data,
            sentiment_data=sentiment_data,
            appraisal_data=appraisal_data,
            transcript_segments=state["transcript_segments"],
        )
        tasks.append(task)

    # Run all frameworks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect results
    framework_results = {}
    framework_errors = {}

    for fw_id, result in zip(fw_ids, results):
        if isinstance(result, Exception):
            framework_errors[fw_id] = str(result)
        elif result is not None:
            # Serialize FrameworkOutput to dict for TypedDict compatibility
            dumped = result.model_dump()
            # Normalize severity to string for downstream nodes
            from signalapp.domain.framework import normalize_severity
            dumped["severity"] = normalize_severity(dumped.get("severity", "green"))
            framework_results[fw_id] = dumped
        else:
            framework_errors[fw_id] = "No output returned"

    return {
        "framework_results": framework_results,
        "framework_errors": framework_errors,
    }


async def _run_framework(
    provider: GeminiProvider,
    fw_id: int,
    group_id: str,
    module_path: str,
    output_class_name: str,
    llm_config: LLMConfig,
    transcript_text: str,
    call_type: str = "other",
    hedge_data: list = None,
    sentiment_data: list = None,
    appraisal_data: list = None,
    transcript_segments: list = None,
):
    """Run a single framework LLM call and return FrameworkOutput."""
    import importlib
    import json

    # Dynamically load prompt module
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return _stub_framework_output(fw_id, f"Prompt module not found: {module_path}")

    output_class = getattr(module, output_class_name, None)
    if output_class is None:
        return _stub_framework_output(fw_id, f"Output class {output_class_name} not found in {module_path}")

    system_prompt = getattr(module, "SYSTEM_PROMPT", "")
    user_template = getattr(module, "USER_PROMPT", "")

    # Format user prompt with pass1 data + call_type
    format_kwargs = {
        "transcript_text": transcript_text,
        "pass1_hedge_data": json.dumps(hedge_data or [], indent=2) if hedge_data else "None",
        "pass1_sentiment_data": json.dumps(sentiment_data or [], indent=2) if sentiment_data else "None",
        "pass1_appraisal_data": json.dumps(appraisal_data or [], indent=2) if appraisal_data else "None",
    }
    # Add call_type if the template uses it (e.g., NEPQ prompt)
    if "{call_type}" in user_template:
        format_kwargs["call_type"] = call_type
    user_prompt = user_template.format(**format_kwargs)

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # ── Attempt with retry ──────────────────────────────────────────────────
    last_error = ""
    for attempt in range(3):
        try:
            result = await provider.complete_structured(
                prompt=full_prompt,
                response_model=output_class,
                config=llm_config,
            )
            # Truncate headline if too long
            if hasattr(result, "headline") and result.headline and len(result.headline) > 120:
                result.headline = result.headline[:117] + "..."
            return _to_framework_output(fw_id, result, transcript_segments)
        except Exception as e:
            last_error = str(e)[:200]
            logger.warning(f"[execute_groups] FW-{fw_id} attempt {attempt+1} failed: {last_error[:100]}")

            # Try partial extraction from raw text on last attempt
            if attempt == 2:
                try:
                    raw_text = _get_raw_response_text(provider, full_prompt, None, llm_config)
                    partial = _try_partial_extraction(output_class, raw_text, fw_id)
                    if partial is not None:
                        logger.info(f"[execute_groups] FW-{fw_id}: using partial extraction")
                        return partial
                except Exception:
                    pass

            # Don't append to prompt — just retry with same prompt
            continue

    # All retries exhausted — return stub
    logger.warning(f"[execute_groups] FW-{fw_id} all attempts failed: {last_error}")
    return _stub_framework_output(fw_id, f"LLM call failed: {last_error}")


def _to_framework_output(fw_id: int, raw_result, transcript_segments: list = None) -> FrameworkOutput:
    """Convert a Pydantic output model to a FrameworkOutput."""
    from signalapp.domain.framework import FrameworkOutput as FO, Severity

    # Map severity string to enum
    sev = raw_result.severity if hasattr(raw_result, "severity") else "green"
    try:
        severity_enum = Severity(sev)
    except ValueError:
        severity_enum = Severity.YELLOW

    # Extract score
    score = None
    if hasattr(raw_result, "health_score"):
        score = raw_result.health_score * 100
    elif hasattr(raw_result, "compliance_score"):
        score = raw_result.compliance_score * 100
    elif hasattr(raw_result, "response_score"):
        score = raw_result.response_score * 100
    elif hasattr(raw_result, "alignment_score"):
        score = raw_result.alignment_score * 100
    elif hasattr(raw_result, "structure_score"):
        score = raw_result.structure_score * 100
    elif hasattr(raw_result, "urgency_score"):
        score = raw_result.urgency_score * 100
    elif hasattr(raw_result, "buyer_leverage_score"):
        score = raw_result.buyer_leverage_score * 100
    elif hasattr(raw_result, "nepq_score"):
        score = raw_result.nepq_score * 100

    # Get AIM output if present
    aim_output = None
    is_aim_null = False
    if hasattr(raw_result, "is_aim_null_finding"):
        is_aim_null = raw_result.is_aim_null_finding
    if hasattr(raw_result, "aim_output"):
        aim_output = raw_result.aim_output

    # Get canonical framework name from registry
    from signalapp.domain.frameworks import get_framework_name
    canonical_name = get_framework_name(fw_id)

    # Extract evidence from raw result if available
    evidence_list = []
    raw_evidence = getattr(raw_result, "evidence", []) or []
    for ev in raw_evidence:
        if hasattr(ev, "model_dump"):
            ev_dict = ev.model_dump()
        elif isinstance(ev, dict):
            ev_dict = ev
        else:
            continue
        evidence_list.append({
            "segment_id": ev_dict.get("segment_id", ""),
            "start_time_ms": ev_dict.get("start_time_ms", 0),
            "speaker": ev_dict.get("speaker", ""),
            "text_excerpt": ev_dict.get("text_excerpt", ""),
        })

    explanation = getattr(raw_result, "explanation", "")
    coaching = getattr(raw_result, "coaching_recommendation", "")

    if transcript_segments:
        # Fill empty text_excerpts by looking up actual segment text
        _fill_empty_excerpts(evidence_list, transcript_segments)

        # Mine additional evidence from explanation/coaching text
        # Run as supplement (not just fallback) when evidence is sparse
        if len(evidence_list) < 3:
            mined = _extract_evidence_from_text(explanation, coaching, transcript_segments)
            seen_ids = {e.get("segment_id") for e in evidence_list if e.get("segment_id")}
            for m in mined:
                if m.get("segment_id") not in seen_ids and len(evidence_list) < 8:
                    evidence_list.append(m)
                    seen_ids.add(m.get("segment_id"))

    # Build FrameworkOutput
    return FO(
        framework_id=f"FW-{fw_id:02d}",
        framework_name=canonical_name,
        score=score,
        severity=severity_enum,
        confidence=getattr(raw_result, "confidence", 0.5),
        headline=getattr(raw_result, "headline", f"Framework {fw_id} result"),
        explanation=explanation,
        evidence=evidence_list,
        coaching_recommendation=coaching,
        raw_analysis=raw_result.model_dump() if hasattr(raw_result, "model_dump") else {},
        is_aim_null_finding=is_aim_null,
        aim_output=aim_output,
    )


def _stub_framework_output(fw_id: int, error: str) -> FrameworkOutput:
    """Return a stub FrameworkOutput when LLM call fails."""
    from signalapp.domain.framework import FrameworkOutput, Severity

    return FrameworkOutput(
        framework_id=f"FW-{fw_id:02d}",
        framework_name=f"Framework {fw_id}",
        score=None,
        severity=Severity.YELLOW,
        confidence=0.0,
        headline=f"Analysis unavailable",
        explanation=f"Analysis could not be completed: {error}",
        evidence=[],
        coaching_recommendation="Unable to generate recommendation.",
        raw_analysis={"error": error},
        is_aim_null_finding=False,
    )


def _fill_empty_excerpts(evidence_list: list[dict], transcript_segments: list[dict]):
    """Fill empty text_excerpt fields by looking up actual segment text."""
    seg_lookup = {}
    for seg in transcript_segments:
        sid = seg.get("segment_id", "")
        if sid:
            seg_lookup[sid] = seg
        # Also index by segment_index patterns like "seg_3", "segment_3"
        idx = seg.get("segment_index")
        if idx is not None:
            seg_lookup[f"seg_{idx}"] = seg
            seg_lookup[f"segment_{idx}"] = seg

    for ev in evidence_list:
        if ev.get("text_excerpt"):
            continue
        # Try to find the segment
        sid = ev.get("segment_id", "")
        seg = seg_lookup.get(sid)
        if seg:
            ev["text_excerpt"] = seg.get("text", "")[:150]
            ev["speaker"] = ev.get("speaker") or seg.get("speaker_name", "")
            ev["start_time_ms"] = ev.get("start_time_ms") or seg.get("start_time_ms", 0)


def _extract_evidence_from_text(
    explanation: str, coaching: str, transcript_segments: list[dict]
) -> list[dict]:
    """
    Mine evidence from LLM explanation/coaching text.

    Three strategies:
    1. [MM:SS] timestamps — find segment closest to timestamp, grab nearby quote
    2. Segment references — "segment 3", "seg_5", "at segment 10"
    3. Quoted phrases — fuzzy-match against transcript segments
    """
    import re
    from signalapp.pipeline.intelligence.quote_verify import verify_quote

    if not transcript_segments:
        return []

    combined = f"{explanation}\n{coaching}"
    if not combined.strip():
        return []

    evidence = []
    seen_segments = set()

    # Build index for fast segment lookup
    seg_by_index = {}
    for seg in transcript_segments:
        idx = seg.get("segment_index")
        if idx is not None:
            seg_by_index[idx] = seg

    # Strategy 1: Find [MM:SS] timestamps and grab nearby quoted text
    ts_pattern = re.compile(r'\[(\d{1,3}):(\d{2})\]')
    quote_pattern = re.compile(r"""['"\u201c\u201d]([^'"\u201c\u201d]{8,200})['"\u201c\u201d]""")

    for ts_match in ts_pattern.finditer(combined):
        if len(evidence) >= 8:
            break
        mins, secs = int(ts_match.group(1)), int(ts_match.group(2))
        ts_ms = mins * 60000 + secs * 1000

        best_seg = None
        best_dist = float("inf")
        for seg in transcript_segments:
            dist = abs(seg.get("start_time_ms", 0) - ts_ms)
            if dist < best_dist:
                best_dist = dist
                best_seg = seg

        if best_seg and best_dist < 15000:
            seg_id = best_seg.get("segment_id", "")
            if seg_id in seen_segments:
                continue
            seen_segments.add(seg_id)

            # Look for a quote near this timestamp
            nearby_start = max(0, ts_match.start() - 30)
            nearby_end = min(len(combined), ts_match.end() + 400)
            nearby_text = combined[nearby_start:nearby_end]

            quote_text = ""
            qm = quote_pattern.search(nearby_text)
            if qm:
                quote_text = qm.group(1).strip()
            if not quote_text:
                quote_text = best_seg.get("text", "")[:150]

            evidence.append({
                "segment_id": seg_id,
                "start_time_ms": best_seg.get("start_time_ms", 0),
                "speaker": best_seg.get("speaker_name", ""),
                "text_excerpt": quote_text,
            })

    # Strategy 2: Find segment index references ("segment 3", "seg 5", "at segment 10")
    seg_ref_pattern = re.compile(r'(?:segment|seg)[_\s]*(\d{1,3})', re.IGNORECASE)
    for ref_match in seg_ref_pattern.finditer(combined):
        if len(evidence) >= 8:
            break
        seg_idx = int(ref_match.group(1))
        seg = seg_by_index.get(seg_idx)
        if seg:
            seg_id = seg.get("segment_id", "")
            if seg_id in seen_segments:
                continue
            seen_segments.add(seg_id)

            # Look for a nearby quote
            nearby_start = max(0, ref_match.start() - 30)
            nearby_end = min(len(combined), ref_match.end() + 400)
            nearby_text = combined[nearby_start:nearby_end]

            quote_text = ""
            qm = quote_pattern.search(nearby_text)
            if qm:
                quote_text = qm.group(1).strip()
            if not quote_text:
                quote_text = seg.get("text", "")[:150]

            evidence.append({
                "segment_id": seg_id,
                "start_time_ms": seg.get("start_time_ms", 0),
                "speaker": seg.get("speaker_name", ""),
                "text_excerpt": quote_text,
            })

    # Strategy 3: Match quoted phrases directly via fuzzy matching
    for qm in quote_pattern.finditer(combined):
        if len(evidence) >= 8:
            break
        quote_text = qm.group(1).strip()
        if len(quote_text) < 12:
            continue
        score, seg_id, actual_text = verify_quote(
            quote_text, transcript_segments, threshold=0.50
        )
        if score >= 0.50 and seg_id and seg_id not in seen_segments:
            seen_segments.add(seg_id)
            matched_seg = next(
                (s for s in transcript_segments if s.get("segment_id") == seg_id), {}
            )
            evidence.append({
                "segment_id": seg_id,
                "start_time_ms": matched_seg.get("start_time_ms", 0),
                "speaker": matched_seg.get("speaker_name", ""),
                "text_excerpt": actual_text or quote_text,
            })

    return evidence[:8]


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


# ── Partial extraction helpers (PRD: ≥50% fields valid → use partial results) ───

import json
import re


def _get_raw_response_text(provider, prompt: str, config, llm_config) -> str | None:
    """Get the raw response text from the provider for partial parsing."""
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
        logger.warning(f"_get_raw_response_text failed: {type(e).__name__}: {e}")
        return None


def _try_partial_extraction(output_class, raw_text: str, fw_id: int):
    """Try to extract valid fields from raw JSON text when Pydantic validation fails."""
    if not raw_text:
        return None

    # Strip markdown code fences if present
    text = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
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

    # Build a partial FrameworkOutput with whatever fields parse correctly
    from signalapp.domain.framework import FrameworkOutput as FO, Severity

    # Truncate headline if needed
    headline = data.get("headline", f"Framework {fw_id}")
    if len(headline) > 80:
        headline = headline[:77] + "..."

    # Map severity
    sev = data.get("severity", "green")
    try:
        severity_enum = Severity(sev)
    except (ValueError, TypeError):
        severity_enum = Severity.YELLOW

    # Extract score from whichever field exists
    score = None
    for score_key in ["health_score", "compliance_score", "response_score",
                       "alignment_score", "structure_score", "urgency_score",
                       "buyer_leverage_score"]:
        val = data.get(score_key)
        if val is not None:
            score = float(val) * 100
            break

    # Get evidence / instances
    evidence = data.get("evidence") or data.get("commitment_instances") or data.get("timing_signals") or []
    if evidence and isinstance(evidence, list) and len(evidence) > 0:
        first_item = evidence[0] if isinstance(evidence[0], dict) else {}
        clean_evidence = [
            {
                "segment_id": e.get("segment_id", ""),
                "start_time_ms": e.get("timestamp", e.get("start_time_ms", 0)),
                "speaker": e.get("speaker", ""),
                "text_excerpt": e.get("quote", e.get("text_excerpt", "")),
            }
            for e in evidence[:5]
            if isinstance(e, dict)
        ]
    else:
        clean_evidence = []

    # Coaching
    coaching = data.get("coaching_recommendation", "")

    # Only return if we have meaningful content
    explanation = data.get("explanation", "")
    if not headline and not explanation:
        return None

    return FO(
        framework_id=f"FW-{fw_id:02d}",
        framework_name=headline[:40],
        score=score,
        severity=severity_enum,
        confidence=float(data.get("confidence", 0.5)),
        headline=headline,
        explanation=explanation,
        evidence=clean_evidence,
        coaching_recommendation=coaching,
        raw_analysis=data,
        is_aim_null_finding=bool(data.get("is_aim_null_finding")),
        aim_output=data.get("aim_output"),
    )


def _count_valid_fields(framework_output: "FrameworkOutput", output_class) -> int:
    """Count how many fields in the output_class are non-null/non-empty in the result."""
    from signalapp.domain.framework import FrameworkOutput

    if not isinstance(framework_output, FrameworkOutput):
        return 0

    count = 0
    # Check core required fields
    if framework_output.headline and framework_output.headline != "Analysis unavailable":
        count += 1
    if framework_output.explanation and "could not be completed" not in framework_output.explanation:
        count += 1
    if framework_output.coaching_recommendation and "Unable to generate" not in framework_output.coaching_recommendation:
        count += 1
    if framework_output.confidence and framework_output.confidence > 0:
        count += 1
    if framework_output.severity:
        count += 1
    return count


def _total_schema_fields(output_class) -> int:
    """Return the number of expected fields in the output schema."""
    if hasattr(output_class, "model_fields"):
        return len(output_class.model_fields)
    return 7  # conservative default

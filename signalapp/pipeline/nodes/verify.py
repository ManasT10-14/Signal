"""
Verification node — 7-gate quality checks on framework results.

Each gate validates a quality criterion. Results with low scores
are flagged or downgraded. This runs after framework execution
and before insight generation.

Intelligence layer features:
  - Quote fuzzy matching against transcript (Gate 2)
  - Segment ID validation (Gate 2)
  - Timestamp resolution from DB (Gate 2)
  - Calibrated confidence scoring (Gate 4)
  - Minimum evidence requirements with auto-downgrade (Gate 3)
"""
from __future__ import annotations

import logging

from signalapp.domain.framework import normalize_severity
from signalapp.pipeline.intelligence.quote_verify import verify_evidence_list
from signalapp.pipeline.intelligence.confidence import (
    compute_calibrated_confidence,
    compute_cross_framework_agreement,
)
from signalapp.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

VERIFICATION_GATES = [
    "gate_evidence_presence",      # Gate 1: Evidence exists
    "gate_citation_quality",       # Gate 2: Citations are verbatim + segment validation
    "gate_severity_consistency",   # Gate 3: Severity matches evidence + auto-downgrade
    "gate_confidence_calibration", # Gate 4: Calibrated confidence scoring
    "gate_null_handling",          # Gate 5: AIM null findings handled correctly
    "gate_coherence",              # Gate 6: Output is internally consistent
    "gate_completeness",           # Gate 7: All required fields present
]


async def verify_node(state: PipelineState) -> dict:
    """
    Run 7-gate verification on framework results with intelligence layer.

    Inputs: framework_results, transcript_segments
    Outputs: verified_insights (preliminary), verification_flags
    """
    framework_results = state["framework_results"]
    transcript_segments = state.get("transcript_segments", [])
    call_id = state["call_id"]

    # Build segment lookup for validation
    valid_segment_ids = {seg.get("segment_id") for seg in transcript_segments if seg.get("segment_id")}
    segment_lookup = {seg.get("segment_id"): seg for seg in transcript_segments if seg.get("segment_id")}

    verified_insights = []
    verification_flags = []

    for fw_id, result in framework_results.items():
        evidence = result.get("evidence", [])
        is_aim_null = result.get("is_aim_null_finding", False)
        confidence = result.get("confidence", 0.0)
        headline = result.get("headline", "")

        # Skip stubs from failed LLM calls — don't waste verification on them
        if headline == "Analysis unavailable" or (confidence == 0.0 and not is_aim_null):
            continue
        explanation = result.get("explanation", "")
        coaching = result.get("coaching_recommendation", "")
        severity_val = result.get("severity", "green")
        from signalapp.domain.frameworks import get_framework_name
        framework_name = result.get("framework_name") or get_framework_name(fw_id)
        aim_output = result.get("aim_output")
        raw_analysis = result.get("raw_analysis", {})

        severity_str = normalize_severity(severity_val)

        # ── Gate 1: Evidence presence ────────────────────────────────────────
        if not evidence and not is_aim_null:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_evidence_presence",
                "severity": "warning",
                "message": "No evidence provided but not marked as AIM null",
            })

        # ── Gate 2: Citation quality + segment validation + quote verification ─
        # Validate segment IDs
        validated_evidence = []
        for e in evidence:
            ev = dict(e) if isinstance(e, dict) else {"segment_id": getattr(e, "segment_id", ""),
                                                       "start_time_ms": getattr(e, "start_time_ms", 0),
                                                       "speaker": getattr(e, "speaker", ""),
                                                       "text_excerpt": getattr(e, "text_excerpt", "")}
            seg_id = ev.get("segment_id", "")
            if seg_id and seg_id not in valid_segment_ids:
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_citation_quality",
                    "severity": "warning",
                    "message": f"Invalid segment_id: {seg_id} — hallucinated reference removed",
                })
                continue
            # Resolve timestamp from DB if segment exists
            if seg_id and seg_id in segment_lookup:
                seg = segment_lookup[seg_id]
                ev["timestamp"] = seg.get("start_time_ms", 0)
                ev["start_time_ms"] = seg.get("start_time_ms", 0)
                if not ev.get("speaker"):
                    ev["speaker"] = seg.get("speaker_name", "")
            validated_evidence.append(ev)

        # Run fuzzy quote verification on validated evidence
        verified_ev = verify_evidence_list(validated_evidence, transcript_segments)

        # Compute average quote match score for confidence calibration
        match_scores = [e.get("quote_match_score", 0.0) for e in verified_ev if e.get("quote_match_score")]
        avg_quote_match = sum(match_scores) / len(match_scores) if match_scores else 0.0

        # Flag suspiciously short quotes
        for e in verified_ev:
            quote = e.get("quote") or e.get("text_excerpt", "")
            if quote and len(quote.strip()) < 10:
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_citation_quality",
                    "severity": "info",
                    "message": f"Evidence quote is very short: '{quote[:20]}'",
                })

        # ── Gate 3: Severity consistency + auto-downgrade ────────────────────
        verified_count = len(verified_ev)

        # RED severity requires 2+ verified evidence items
        if severity_str == "red" and verified_count < 2 and not is_aim_null:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_severity_consistency",
                "severity": "downgrade",
                "message": f"RED downgraded to ORANGE — only {verified_count} verified evidence items (need 2+)",
            })
            severity_str = "orange"

        # ORANGE severity requires at least 1 verified evidence item
        if severity_str == "orange" and verified_count == 0 and not is_aim_null:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_severity_consistency",
                "severity": "downgrade",
                "message": "ORANGE downgraded to YELLOW — no verified evidence",
            })
            severity_str = "yellow"

        # Green severity should not have strong negative evidence in explanation
        if severity_str == "green" and ("concern" in explanation.lower() or "issue" in explanation.lower()):
            if "minor" not in explanation.lower() and "minimal" not in explanation.lower():
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_severity_consistency",
                    "severity": "info",
                    "message": "GREEN severity but explanation mentions concerns — verify alignment",
                })

        # ── Gate 4: Calibrated confidence ────────────────────────────────────
        cross_agreement = compute_cross_framework_agreement(fw_id, severity_str, framework_results)
        calibrated = compute_calibrated_confidence(
            evidence_count=verified_count,
            avg_quote_match=avg_quote_match,
            pattern_recurrence=max(1, verified_count),
            alternative_explanations=0,
            cross_framework_agreement=cross_agreement,
            raw_confidence=confidence,
            severity=severity_str,
            explanation_length=len(explanation),
        )

        # Flag if raw confidence was very different from calibrated
        if abs(confidence - calibrated) > 0.25:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_confidence_calibration",
                "severity": "info",
                "message": f"Confidence recalibrated: {confidence:.2f} → {calibrated:.2f}",
            })

        # ── Gate 5: Null handling ────────────────────────────────────────────
        if is_aim_null and not aim_output:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_null_handling",
                "severity": "error",
                "message": "AIM null finding without AIM output explanation",
            })
        if is_aim_null and aim_output and severity_str not in ("green", "yellow"):
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_null_handling",
                "severity": "warning",
                "message": "AIM null finding should typically be green/yellow severity",
            })

        # ── Gate 6: Coherence ────────────────────────────────────────────────
        if headline and explanation:
            headline_words = set(headline.lower().split())
            explanation_lower = explanation.lower()

            positive_indicators = {"good", "strong", "healthy", "positive", "leverage"}
            negative_indicators = {"concern", "problem", "weak", "risk", "issue", "warning"}

            headline_positive = any(w in headline_words for w in positive_indicators)
            explanation_negative = any(w in negative_indicators for w in explanation_lower.split())

            if headline_positive and explanation_negative:
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_coherence",
                    "severity": "warning",
                    "message": "Headline is positive but explanation contains negative language",
                })

        # ── Gate 7: Completeness ─────────────────────────────────────────────
        missing_fields = []
        if not headline:
            missing_fields.append("headline")
        if not explanation:
            missing_fields.append("explanation")
        if not coaching:
            missing_fields.append("coaching_recommendation")

        if missing_fields:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_completeness",
                "severity": "error",
                "message": f"Missing fields: {missing_fields}",
            })

        # ── Build verified insight dict ──────────────────────────────────────
        if headline and explanation:
            evidence_list = []
            for e in verified_ev:
                evidence_list.append({
                    "segment_id": e.get("segment_id", ""),
                    "timestamp": e.get("start_time_ms", e.get("timestamp", 0)),
                    "speaker": e.get("speaker", ""),
                    "quote": e.get("quote") or e.get("text_excerpt", ""),
                    "quote_match_score": e.get("quote_match_score", 0.0),
                    "quote_verified": e.get("quote_verified", False),
                })

            insight_dict = {
                "insight_id": f"{call_id}-fw{fw_id}",
                "call_id": call_id,
                "framework_result_id": f"FW-{fw_id:02d}",
                "priority_rank": 0,
                "framework_name": framework_name,
                "severity": severity_str,
                "confidence": calibrated,
                "raw_confidence": confidence,
                "headline": headline,
                "explanation": explanation,
                "evidence": evidence_list,
                "coaching_recommendation": coaching,
                "created_at": "",
                "is_top_insight": False,
                "is_aim_null_finding": is_aim_null,
            }
            verified_insights.append(insight_dict)

    return {
        "verified_insights": verified_insights,
        "_verification_flags": verification_flags,
    }

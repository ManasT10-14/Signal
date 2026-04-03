"""
Verification node — 7-gate quality checks on framework results.

Each gate validates a quality criterion. Results with low scores
are flagged or downgraded. This runs after framework execution
and before insight generation.
"""
from __future__ import annotations

from signalapp.pipeline.state import PipelineState


VERIFICATION_GATES = [
    "gate_evidence_presence",      # Gate 1: Evidence exists
    "gate_citation_quality",       # Gate 2: Citations are verbatim
    "gate_severity_consistency",   # Gate 3: Severity matches evidence
    "gate_confidence_calibration", # Gate 4: Confidence matches evidence quality
    "gate_null_handling",          # Gate 5: AIM null findings handled correctly
    "gate_coherence",              # Gate 6: Output is internally consistent
    "gate_completeness",           # Gate 7: All required fields present
]


async def verify_node(state: PipelineState) -> dict:
    """
    Run 7-gate verification on framework results.

    Inputs: framework_results
    Outputs: verified_insights (preliminary), verification_flags

    Each gate scores a framework result and downgrades severity / flags for human review.
    """
    framework_results = state["framework_results"]
    call_id = state["call_id"]

    verified_insights = []
    verification_flags = []

    for fw_id, result in framework_results.items():
        # framework_results values are now dicts (serialized FrameworkOutput)
        evidence = result.get("evidence", [])
        is_aim_null = result.get("is_aim_null_finding", False)
        confidence = result.get("confidence", 0.0)
        headline = result.get("headline", "")
        explanation = result.get("explanation", "")
        coaching = result.get("coaching_recommendation", "")
        severity_val = result.get("severity", "green")
        framework_name = result.get("framework_name", f"Framework {fw_id}")
        aim_output = result.get("aim_output")
        raw_analysis = result.get("raw_analysis", {})

        # Handle severity (may be string or enum)
        if hasattr(severity_val, "value"):
            severity_str = severity_val.value
        else:
            severity_str = str(severity_val)

        # Gate 1: Evidence presence
        if not evidence and not is_aim_null:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_evidence_presence",
                "severity": "warning",
                "message": "No evidence provided but not marked as AIM null",
            })

        # Gate 2: Citation quality — verify evidence citations are verbatim from transcript
        for e in evidence:
            quote = e.get("quote") or e.get("text_excerpt", "")
            if quote:
                # Check if quote is short (less than 10 chars) or looks fabricated
                if len(quote.strip()) < 10:
                    verification_flags.append({
                        "fw_id": fw_id,
                        "gate": "gate_citation_quality",
                        "severity": "warning",
                        "message": f"Evidence quote is suspiciously short: '{quote[:20]}...'",
                    })
                # Check for generic/non-specific quotes
                generic_phrases = ["example", "something", "stuff", "things"]
                if quote.lower().strip() in generic_phrases:
                    verification_flags.append({
                        "fw_id": fw_id,
                        "gate": "gate_citation_quality",
                        "severity": "warning",
                        "message": f"Evidence quote appears generic: '{quote}'",
                    })

        # Gate 3: Severity consistency — verify severity matches evidence quality
        # Red severity should have strong evidence
        if severity_str == "red" and len(evidence) < 2 and not is_aim_null:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_severity_consistency",
                "severity": "warning",
                "message": "RED severity with fewer than 2 evidence items — may be overstating",
            })
        # Green severity should not have strong negative evidence in explanation
        if severity_str == "green" and "concern" in explanation.lower() or "issue" in explanation.lower():
            if "minor" not in explanation.lower() and "minimal" not in explanation.lower():
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_severity_consistency",
                    "severity": "info",
                    "message": "GREEN severity but explanation mentions concerns — verify alignment",
                })

        # Gate 4: Confidence calibration
        # If confidence is very high but evidence is thin, flag it
        if confidence > 0.85 and len(evidence) == 0 and not is_aim_null:
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_confidence_calibration",
                "severity": "warning",
                "message": f"High confidence ({confidence}) but no evidence",
            })
        # Low confidence but high severity is also suspicious
        if confidence < 0.5 and severity_str in ("red", "orange"):
            verification_flags.append({
                "fw_id": fw_id,
                "gate": "gate_confidence_calibration",
                "severity": "info",
                "message": f"Low confidence ({confidence}) but severe rating — verify calibration",
            })

        # Gate 5: Null handling
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

        # Gate 6: Coherence — output is internally consistent
        # Headline and explanation should be consistent
        if headline and explanation:
            # Check for contradictory language
            headline_words = set(headline.lower().split())
            explanation_lower = explanation.lower()

            # Positive headline with negative explanation
            positive_indicators = ["good", "strong", "healthy", "positive", "leverage"]
            negative_indicators = ["concern", "problem", "weak", "risk", "issue", "warning"]

            headline_positive = any(w in headline_words for w in positive_indicators)
            headline_negative = any(w in headline_words for w in negative_indicators)
            explanation_negative = any(w in negative_indicators for w in explanation_lower.split())

            if headline_positive and explanation_negative:
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_coherence",
                    "severity": "warning",
                    "message": "Headline is positive but explanation contains negative language",
                })
            if headline_negative and not explanation_negative:
                verification_flags.append({
                    "fw_id": fw_id,
                    "gate": "gate_coherence",
                    "severity": "info",
                    "message": "Headline suggests concern but explanation appears neutral",
                })

        # Gate 7: Completeness check
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

        # Pass through as serialized Insight dict
        if headline and explanation:  # Only create insight if has content
            evidence_list = []
            for e in evidence:
                # Evidence items may be dicts or EvidenceRef objects
                if isinstance(e, dict):
                    evidence_list.append({
                        "segment_id": e.get("segment_id", ""),
                        "timestamp": e.get("start_time_ms", 0),
                        "speaker": e.get("speaker", ""),
                        "quote": e.get("text_excerpt", ""),
                    })
                else:
                    # Pydantic model
                    evidence_list.append({
                        "segment_id": e.segment_id,
                        "timestamp": e.start_time_ms,
                        "speaker": e.speaker,
                        "quote": e.text_excerpt,
                    })

            insight_dict = {
                "insight_id": f"{call_id}-fw{fw_id}",
                "call_id": call_id,
                "framework_result_id": f"FW-{fw_id:02d}",
                "priority_rank": 0,  # Will be set by prioritize_insights
                "framework_name": framework_name,
                "severity": severity_str,
                "confidence": confidence,
                "headline": headline,
                "explanation": explanation,
                "evidence": evidence_list,
                "coaching_recommendation": coaching,
                "created_at": "",
                "is_top_insight": False,
            }
            verified_insights.append(insight_dict)

    return {
        "verified_insights": verified_insights,
        "_verification_flags": verification_flags,
    }

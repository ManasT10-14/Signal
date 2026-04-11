"""
Calibrated confidence scoring.

Blends LLM self-reported confidence with evidence quality signals.
When evidence is available, it adjusts confidence up/down based on quality.
When evidence is absent (common with structured output), it trusts
the LLM's confidence more heavily since the LLM still evaluated the transcript.

The key insight: absence of evidence metadata (segment_ids, quotes) doesn't
mean the analysis is wrong — it means the structured output schema didn't
capture evidence details. The LLM still read the transcript and reasoned
about it.
"""
from __future__ import annotations


def compute_calibrated_confidence(
    evidence_count: int = 0,
    avg_quote_match: float = 0.0,
    pattern_recurrence: int = 1,
    alternative_explanations: int = 0,
    cross_framework_agreement: float = 0.0,
    raw_confidence: float = 0.5,
) -> float:
    """Compute calibrated confidence from evidence quality signals.

    When evidence is present: blend raw confidence with evidence quality.
    When evidence is absent: trust raw confidence with a small penalty.
    """
    if evidence_count > 0:
        # Evidence exists — blend raw confidence (60%) with evidence quality (40%)
        evidence_quality = 0.0
        evidence_quality += min(0.30, evidence_count * 0.10)  # more evidence = better
        if avg_quote_match > 0:
            evidence_quality += avg_quote_match * 0.20  # quote match quality
        evidence_quality += min(0.15, max(0, (pattern_recurrence - 1)) * 0.08)
        evidence_quality -= alternative_explanations * 0.05
        evidence_quality += cross_framework_agreement * 0.05
        evidence_quality = max(0.0, min(1.0, evidence_quality + 0.30))  # base evidence quality

        score = (raw_confidence * 0.60) + (evidence_quality * 0.40)
    else:
        # No evidence metadata — trust raw confidence with small penalty
        # The LLM still read the transcript; it just didn't produce segment_ids
        penalty = 0.05  # small penalty for no verifiable evidence
        agreement_boost = cross_framework_agreement * 0.08
        score = raw_confidence - penalty + agreement_boost

    return max(0.0, min(1.0, round(score, 3)))


def compute_cross_framework_agreement(
    fw_id: int,
    severity: str,
    all_results: dict[int, dict],
) -> float:
    """Compute how much other frameworks agree with this one's severity assessment.

    Returns 0.0-1.0 where 1.0 means all other frameworks found similar severity.
    """
    if not all_results or len(all_results) <= 1:
        return 0.0

    severity_is_concerning = severity in ("red", "orange")
    agree_count = 0
    total = 0

    for other_id, other_result in all_results.items():
        if other_id == fw_id:
            continue
        other_sev = other_result.get("severity", "green")
        other_concerning = other_sev in ("red", "orange")
        total += 1
        if severity_is_concerning == other_concerning:
            agree_count += 1

    if total == 0:
        return 0.0

    return round(agree_count / total, 3)

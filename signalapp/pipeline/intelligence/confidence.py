"""
Calibrated confidence scoring.

Replaces raw LLM self-reported confidence with a computed score based on
measurable evidence quality factors (per LLM_RELIABILITY_GUIDE.md).

Formula:
  base = 0.40
  + min(0.20, evidence_count * 0.07)        # more evidence = higher confidence
  + (avg_quote_match - 0.75) * 0.15         # better quote quality
  + min(0.15, (pattern_count - 1) * 0.08)   # recurring patterns
  - alternative_explanations * 0.08          # alternatives reduce confidence
  + cross_framework_agreement * 0.05         # corroboration
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

    Args:
        evidence_count: Number of verified evidence items
        avg_quote_match: Average fuzzy match score of evidence quotes (0-1)
        pattern_recurrence: How many times the pattern repeats in transcript
        alternative_explanations: Number of innocent alternative explanations
        cross_framework_agreement: Agreement with other frameworks (0-1)
        raw_confidence: Original LLM self-reported confidence (used as tiebreaker)

    Returns:
        Calibrated confidence score (0.0 - 1.0)
    """
    score = 0.40  # base

    # Evidence count contribution (up to 0.20)
    score += min(0.20, evidence_count * 0.07)

    # Quote match quality contribution
    if avg_quote_match > 0:
        score += (avg_quote_match - 0.75) * 0.15

    # Pattern recurrence contribution (up to 0.15)
    score += min(0.15, max(0, (pattern_recurrence - 1)) * 0.08)

    # Alternative explanations penalty
    score -= alternative_explanations * 0.08

    # Cross-framework agreement boost
    score += cross_framework_agreement * 0.05

    # Use raw confidence as small tiebreaker (5% weight)
    score += (raw_confidence - 0.5) * 0.05

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

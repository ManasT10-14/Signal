"""
Calibrated confidence scoring.

Blends LLM self-reported confidence with evidence quality signals and
additional contextual signals (severity, explanation depth, cross-framework
agreement) to produce a well-spread confidence score.

Evidence-present path: 60% raw + 40% evidence quality.
Evidence-absent path: uses raw confidence with adjustments for severity
coherence, explanation depth, and cross-framework agreement to ensure
meaningful spread across insights.
"""
from __future__ import annotations


def compute_calibrated_confidence(
    evidence_count: int = 0,
    avg_quote_match: float = 0.0,
    pattern_recurrence: int = 1,
    alternative_explanations: int = 0,
    cross_framework_agreement: float = 0.0,
    raw_confidence: float = 0.5,
    severity: str = "green",
    explanation_length: int = 0,
) -> float:
    """Compute calibrated confidence from evidence quality signals.

    When evidence is present: blend raw confidence with evidence quality.
    When evidence is absent: use multiple contextual signals for spread.
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
        # No evidence metadata — use multiple signals for meaningful spread
        score = raw_confidence

        # Signal 1: Explanation depth proxy
        # Longer, more detailed explanations suggest deeper analysis
        if explanation_length > 500:
            score += 0.03
        elif explanation_length > 200:
            pass  # neutral
        elif explanation_length < 100:
            score -= 0.05

        # Signal 2: Severity-confidence coherence
        # Red/orange findings with low raw confidence should be penalized
        # Green findings with high confidence should be slightly boosted
        if severity in ("red", "orange") and raw_confidence < 0.65:
            score -= 0.08  # alarming finding but LLM wasn't confident
        elif severity in ("red", "orange") and raw_confidence > 0.85:
            score += 0.02  # strong conviction on critical finding
        elif severity == "green" and raw_confidence > 0.80:
            score += 0.02  # confident positive finding

        # Signal 3: Cross-framework agreement (stronger effect than before)
        if cross_framework_agreement > 0.6:
            score += 0.06  # many frameworks agree
        elif cross_framework_agreement < 0.3:
            score -= 0.04  # frameworks disagree

        # Signal 4: Small base penalty for no verifiable evidence
        score -= 0.03

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

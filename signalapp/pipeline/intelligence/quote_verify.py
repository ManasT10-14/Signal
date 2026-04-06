"""
Quote verification via fuzzy string matching.

Verifies that LLM-cited evidence quotes actually appear in the transcript.
Uses difflib.SequenceMatcher (stdlib) — no external dependencies.

Thresholds (from LLM_RELIABILITY_GUIDE.md):
  >= 0.75  verified (use as-is)
  0.55-0.75  partial match (replace quote with actual segment text)
  < 0.55  likely hallucinated (suppress evidence item)
"""
from __future__ import annotations

from difflib import SequenceMatcher


def verify_quote(
    quote: str,
    transcript_segments: list[dict],
    threshold: float = 0.55,
) -> tuple[float, str | None, str | None]:
    """Verify an evidence quote against transcript segments.

    Returns:
        (match_score, matched_segment_id, actual_text)
        - match_score: 0.0-1.0 similarity
        - matched_segment_id: ID of best-matching segment (or None)
        - actual_text: the actual segment text (for replacement on partial match)
    """
    if not quote or not quote.strip():
        return 0.0, None, None

    quote_lower = quote.strip().lower()
    best_score = 0.0
    best_segment_id = None
    best_text = None

    for seg in transcript_segments:
        seg_text = seg.get("text", "")
        if not seg_text:
            continue

        seg_lower = seg_text.strip().lower()

        # Try full sequence match
        score = SequenceMatcher(None, quote_lower, seg_lower).ratio()

        # Also check if the quote is a substring of the segment
        if quote_lower in seg_lower:
            score = max(score, 0.85)
        elif seg_lower in quote_lower and len(seg_lower) > 20:
            score = max(score, 0.75)

        if score > best_score:
            best_score = score
            best_segment_id = seg.get("segment_id")
            best_text = seg_text

    if best_score < threshold:
        return best_score, None, None

    return best_score, best_segment_id, best_text


def verify_evidence_list(
    evidence: list[dict],
    transcript_segments: list[dict],
) -> list[dict]:
    """Verify all evidence items and annotate with match quality.

    Returns a new list of evidence dicts with added fields:
      - quote_match_score: 0.0-1.0
      - quote_verified: bool
      - original_quote: preserved if replaced

    Hallucinated evidence (score < 0.55) is removed.
    Partial matches (0.55-0.75) have quotes replaced with actual text.
    """
    verified = []

    for ev in evidence:
        quote = ev.get("quote") or ev.get("text_excerpt", "")
        if not quote:
            # No quote to verify — keep but flag
            ev_copy = dict(ev)
            ev_copy["quote_match_score"] = 0.0
            ev_copy["quote_verified"] = False
            verified.append(ev_copy)
            continue

        score, seg_id, actual_text = verify_quote(quote, transcript_segments)

        if score < 0.55:
            # Hallucinated — suppress
            continue

        ev_copy = dict(ev)
        ev_copy["quote_match_score"] = round(score, 3)
        ev_copy["quote_verified"] = score >= 0.75

        if score < 0.75 and actual_text:
            # Partial match — replace with actual text
            ev_copy["original_quote"] = quote
            ev_copy["quote"] = actual_text
            ev_copy["text_excerpt"] = actual_text

        if seg_id and not ev_copy.get("segment_id"):
            ev_copy["segment_id"] = seg_id

        verified.append(ev_copy)

    return verified

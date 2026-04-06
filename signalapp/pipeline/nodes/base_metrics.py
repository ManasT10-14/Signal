"""
Base metrics node — computes zero-LLM-cost transcript metrics.

Extracts: talk ratio, question counts, filler density, WPM,
longest monologue, interruptions, response latency, silence %.
"""
from __future__ import annotations

import re
from signalapp.pipeline.state import PipelineState


FILLER_WORDS = {"um", "uh", "like", "you know", "i mean", "sort of", "kind of",
                "basically", "actually", "literally", "right", "so yeah"}


async def base_metrics_node(state: PipelineState) -> dict:
    """Compute base metrics from transcript segments (zero LLM cost)."""
    segments = state.get("transcript_segments", [])

    if not segments:
        return {"base_metrics": _empty_metrics()}

    # Estimate actual speaking duration from word count (~150 WPM average)
    # This is needed because pasted transcripts have start times but no real end times
    AVG_WPM = 150
    for seg in segments:
        words = seg.get("word_count", 0) or len(seg.get("text", "").split())
        speaking_ms = max(int(words / AVG_WPM * 60 * 1000), 500)  # at least 0.5s
        seg["_speaking_ms"] = speaking_ms
        seg["_estimated_end_ms"] = seg.get("start_time_ms", 0) + speaking_ms

    # Categorize segments by role
    rep_segs = [s for s in segments if s.get("speaker_role") == "rep"]
    buyer_segs = [s for s in segments if s.get("speaker_role") == "buyer"]

    # Total duration (from first start to last segment estimated end)
    all_starts = [s.get("start_time_ms", 0) for s in segments]
    all_est_ends = [s.get("_estimated_end_ms", 0) for s in segments]
    total_duration_ms = max(max(all_est_ends), max(s.get("end_time_ms", 0) for s in segments)) - min(all_starts) if segments else 0
    total_duration_s = max(total_duration_ms / 1000, 1.0)

    # Talk time per speaker — use estimated speaking duration
    rep_talk_ms = sum(s.get("_speaking_ms", 0) for s in rep_segs)
    buyer_talk_ms = sum(s.get("_speaking_ms", 0) for s in buyer_segs)
    total_talk_ms = rep_talk_ms + buyer_talk_ms or 1

    # Talk ratio
    rep_talk_ratio = round(rep_talk_ms / total_talk_ms, 3)
    buyer_talk_ratio = round(buyer_talk_ms / total_talk_ms, 3)

    # Word counts
    rep_words = sum(s.get("word_count", 0) or len(s.get("text", "").split()) for s in rep_segs)
    buyer_words = sum(s.get("word_count", 0) or len(s.get("text", "").split()) for s in buyer_segs)

    # WPM — use estimated speaking time
    rep_talk_min = max(rep_talk_ms / 60000, 0.1)
    buyer_talk_min = max(buyer_talk_ms / 60000, 0.1)
    rep_wpm = round(rep_words / rep_talk_min)
    buyer_wpm = round(buyer_words / buyer_talk_min)

    # Questions per speaker
    rep_questions = sum(s.get("text", "").count("?") for s in rep_segs)
    buyer_questions = sum(s.get("text", "").count("?") for s in buyer_segs)

    # Filler word density
    rep_fillers = _count_fillers(" ".join(s.get("text", "") for s in rep_segs))
    buyer_fillers = _count_fillers(" ".join(s.get("text", "") for s in buyer_segs))
    rep_filler_rate = round(rep_fillers / rep_talk_min, 1) if rep_talk_min > 0.1 else 0
    buyer_filler_rate = round(buyer_fillers / buyer_talk_min, 1) if buyer_talk_min > 0.1 else 0

    # Longest monologue (consecutive same-speaker segments)
    rep_longest_ms, rep_longest_start = _longest_monologue(segments, "rep")
    buyer_longest_ms, buyer_longest_start = _longest_monologue(segments, "buyer")

    # Interruptions (speaker change where next segment overlaps)
    interruptions = _count_interruptions(segments)

    # Response latency (average gap between speaker switches)
    rep_latency, buyer_latency = _avg_response_latency(segments)

    # Silence — computed as gaps between estimated_end and next start
    silence_ms = 0
    for i in range(len(segments) - 1):
        gap = segments[i + 1].get("start_time_ms", 0) - segments[i].get("_estimated_end_ms", 0)
        if gap > 0:
            silence_ms += gap
    silence_pct = round(silence_ms / max(total_duration_ms, 1) * 100, 1)

    # Longest silence — using estimated end times
    longest_silence_ms, longest_silence_at = _longest_silence_estimated(segments)

    metrics = {
        "total_duration_seconds": round(total_duration_s, 1),
        "total_segments": len(segments),
        "rep_talk_ratio": rep_talk_ratio,
        "buyer_talk_ratio": buyer_talk_ratio,
        "rep_words": rep_words,
        "buyer_words": buyer_words,
        "rep_wpm": rep_wpm,
        "buyer_wpm": buyer_wpm,
        "rep_questions": rep_questions,
        "buyer_questions": buyer_questions,
        "rep_filler_rate_per_min": rep_filler_rate,
        "buyer_filler_rate_per_min": buyer_filler_rate,
        "rep_longest_monologue_seconds": round(rep_longest_ms / 1000, 1),
        "rep_longest_monologue_at_ms": rep_longest_start,
        "buyer_longest_monologue_seconds": round(buyer_longest_ms / 1000, 1),
        "buyer_longest_monologue_at_ms": buyer_longest_start,
        "interruption_count": interruptions,
        "rep_avg_response_latency_seconds": rep_latency,
        "buyer_avg_response_latency_seconds": buyer_latency,
        "silence_percentage": silence_pct,
        "longest_silence_seconds": round(longest_silence_ms / 1000, 1),
        "longest_silence_at_ms": longest_silence_at,
    }

    return {"base_metrics": metrics}


def _count_fillers(text: str) -> int:
    text_lower = text.lower()
    count = 0
    for filler in FILLER_WORDS:
        if " " in filler:
            count += text_lower.count(filler)
        else:
            count += len(re.findall(r'\b' + re.escape(filler) + r'\b', text_lower))
    return count


def _longest_monologue(segments: list[dict], role: str) -> tuple[int, int]:
    """Find the longest consecutive stretch by a speaker role."""
    best_duration = 0
    best_start = 0
    current_duration = 0
    current_start = 0

    for seg in segments:
        if seg.get("speaker_role") == role:
            dur = seg.get("end_time_ms", 0) - seg.get("start_time_ms", 0)
            if current_duration == 0:
                current_start = seg.get("start_time_ms", 0)
            current_duration += dur
        else:
            if current_duration > best_duration:
                best_duration = current_duration
                best_start = current_start
            current_duration = 0

    if current_duration > best_duration:
        best_duration = current_duration
        best_start = current_start

    return best_duration, best_start


def _count_interruptions(segments: list[dict]) -> int:
    count = 0
    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]
        if prev.get("speaker_role") != curr.get("speaker_role"):
            if curr.get("start_time_ms", 0) < prev.get("end_time_ms", 0):
                count += 1
    return count


def _avg_response_latency(segments: list[dict]) -> tuple[float, float]:
    """Average gap (seconds) when speaker switches to rep / buyer.
    Uses estimated end time for more accurate gap calculation."""
    rep_gaps = []
    buyer_gaps = []

    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]
        if prev.get("speaker_role") == curr.get("speaker_role"):
            continue
        # Use estimated end time if available
        prev_end = prev.get("_estimated_end_ms", prev.get("end_time_ms", 0))
        gap_ms = curr.get("start_time_ms", 0) - prev_end
        gap_s = max(0, gap_ms / 1000)
        if curr.get("speaker_role") == "rep":
            rep_gaps.append(gap_s)
        elif curr.get("speaker_role") == "buyer":
            buyer_gaps.append(gap_s)

    rep_avg = round(sum(rep_gaps) / len(rep_gaps), 1) if rep_gaps else 0.0
    buyer_avg = round(sum(buyer_gaps) / len(buyer_gaps), 1) if buyer_gaps else 0.0
    return rep_avg, buyer_avg


def _longest_silence_estimated(segments: list[dict]) -> tuple[int, int]:
    """Find the longest gap using estimated end times."""
    best_gap = 0
    best_at = 0

    for i in range(1, len(segments)):
        prev_end = segments[i - 1].get("_estimated_end_ms", segments[i - 1].get("end_time_ms", 0))
        gap = segments[i].get("start_time_ms", 0) - prev_end
        if gap > best_gap:
            best_gap = gap
            best_at = prev_end

    return best_gap, best_at


def _empty_metrics() -> dict:
    return {
        "total_duration_seconds": 0, "total_segments": 0,
        "rep_talk_ratio": 0, "buyer_talk_ratio": 0,
        "rep_words": 0, "buyer_words": 0,
        "rep_wpm": 0, "buyer_wpm": 0,
        "rep_questions": 0, "buyer_questions": 0,
        "rep_filler_rate_per_min": 0, "buyer_filler_rate_per_min": 0,
        "rep_longest_monologue_seconds": 0, "rep_longest_monologue_at_ms": 0,
        "buyer_longest_monologue_seconds": 0, "buyer_longest_monologue_at_ms": 0,
        "interruption_count": 0,
        "rep_avg_response_latency_seconds": 0, "buyer_avg_response_latency_seconds": 0,
        "silence_percentage": 0, "longest_silence_seconds": 0, "longest_silence_at_ms": 0,
    }

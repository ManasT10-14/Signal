"""
Preprocessing job — computes base metrics from transcript before pipeline runs.
ARQ enqueues this job after transcription and before pipeline submission.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


async def run_preprocessing_job(ctx: dict, call_id: str) -> dict:
    """
    ARQ job: compute base metrics from transcript.

    Base metrics are computed from the transcript before the behavioral pipeline runs.
    These provide foundational signals like talk ratio, pause density, filler word rate.

    Computed metrics:
    - total_duration_seconds
    - rep_talk_ratio (fraction of talk time that's rep)
    - buyer_talk_ratio
    - words_per_minute_rep
    - words_per_minute_buyer
    - pause_density (pauses > 2s per minute)
    - filler_word_rate (um, uh, like, you know per 100 words)
    - overlap_count (segments with overlapping timestamps)
    - speaker_balance (number of unique speakers)
    - longest_buyer_turn_seconds
    - longest_rep_turn_seconds
    """
    from signalapp.db.repository import (
        CallRepository,
        TranscriptRepository,
        BaseMetricRepository,
        get_session,
    )

    call_uuid = uuid.UUID(call_id)

    try:
        async for session in get_session():
            # Load transcript segments
            transcript_repo = TranscriptRepository()
            segments = await transcript_repo.get_segments_for_call(call_uuid)

            if not segments:
                return {"status": "error", "error": f"No segments found for call {call_id}"}

            # Compute base metrics
            metrics = _compute_base_metrics(segments)

            # Store base metrics
            metric_repo = BaseMetricRepository()
            stored_metrics = []
            for metric_name, metric_value in metrics.items():
                metric = await metric_repo.upsert(
                    call_id=call_uuid,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    computed_from="transcript",
                )
                stored_metrics.append(metric_name)

            # Update call duration if not already set
            call_repo = CallRepository()
            duration = metrics.get("total_duration_seconds", {}).get("value")
            if duration:
                # Duration update would happen here if Call model supported it
                pass

            logger.info(
                f"[preprocessing] Computed {len(stored_metrics)} base metrics for {call_id}"
            )

        return {
            "status": "complete",
            "call_id": call_id,
            "metrics_computed": stored_metrics,
        }

    except Exception as e:
        logger.error(f"[preprocessing] Failed for {call_id}: {e}")
        return {"status": "error", "error": str(e)}


def _compute_base_metrics(segments: list) -> dict[str, dict]:
    """
    Compute base metrics from transcript segments.
    Returns dict of metric_name → metric_value (flexible JSONB shape).
    """
    from signalapp.db.models import TranscriptSegment

    if not segments:
        return {}

    # Ensure we have proper model instances
    seg_list: list[TranscriptSegment] = []
    for s in segments:
        if isinstance(s, TranscriptSegment):
            seg_list.append(s)
        else:
            # Dict — convert to segment-like object
            seg_list.append(s)

    # Sort by start time
    seg_list = sorted(seg_list, key=lambda s: s.start_time_ms)

    # Duration
    total_duration_ms = max(s.end_time_ms for s in seg_list) - min(s.start_time_ms for s in seg_list)
    total_duration_seconds = total_duration_ms / 1000

    # Talk time per speaker
    rep_talk_ms = sum(
        s.end_time_ms - s.start_time_ms
        for s in seg_list if s.speaker_role == "rep"
    )
    buyer_talk_ms = sum(
        s.end_time_ms - s.start_time_ms
        for s in seg_list if s.speaker_role == "buyer"
    )
    total_talk_ms = rep_talk_ms + buyer_talk_ms or 1

    # Word counts
    rep_words = sum(s.word_count or 0 for s in seg_list if s.speaker_role == "rep")
    buyer_words = sum(s.word_count or 0 for s in seg_list if s.speaker_role == "buyer")
    total_words = rep_words + buyer_words

    # Words per minute
    duration_minutes = total_duration_seconds / 60 or 1
    wpm_rep = round(rep_words / duration_minutes, 1)
    wpm_buyer = round(buyer_words / duration_minutes, 1)

    # Unique speakers
    unique_speakers = len(set(s.speaker_name for s in seg_list))

    # Longest turn
    rep_turns = [
        s.end_time_ms - s.start_time_ms
        for s in seg_list if s.speaker_role == "rep"
    ]
    buyer_turns = [
        s.end_time_ms - s.start_time_ms
        for s in seg_list if s.speaker_role == "buyer"
    ]

    # Filler word rate (per 100 words)
    filler_words = {"um", "uh", "like", "you know", "basically", "actually", "literally"}
    all_text = " ".join(s.text_content if hasattr(s, "text_content") else s.get("text_content", "") for s in seg_list).lower()
    words = all_text.split()
    filler_count = sum(1 for w in words if w in filler_words)
    filler_rate = round(filler_count / (len(words) / 100), 2) if words else 0

    # Pause detection (gaps > 2s between consecutive segments from same speaker)
    pause_ms_threshold = 2000
    pause_count = 0
    for i in range(1, len(seg_list)):
        prev = seg_list[i - 1]
        curr = seg_list[i]
        if curr.speaker_role == prev.speaker_role:
            gap = curr.start_time_ms - prev.end_time_ms
            if gap > pause_ms_threshold:
                pause_count += 1

    pause_density = round(pause_count / duration_minutes, 2) if duration_minutes > 0 else 0

    # Overlap detection (same time range as previous segment — simple check)
    overlap_count = sum(
        1 for i in range(1, len(seg_list))
        if seg_list[i].start_time_ms < seg_list[i - 1].end_time_ms
    )

    return {
        "total_duration_seconds": {"value": round(total_duration_seconds, 1)},
        "rep_talk_ratio": {"value": round(rep_talk_ms / total_talk_ms, 3)},
        "buyer_talk_ratio": {"value": round(buyer_talk_ms / total_talk_ms, 3)},
        "words_per_minute_rep": {"value": wpm_rep},
        "words_per_minute_buyer": {"value": wpm_buyer},
        "total_words": {"value": total_words},
        "rep_words": {"value": rep_words},
        "buyer_words": {"value": buyer_words},
        "pause_density_per_minute": {"value": pause_density},
        "pause_count": {"value": pause_count},
        "filler_word_rate_per_100_words": {"value": filler_rate},
        "overlap_count": {"value": overlap_count},
        "unique_speaker_count": {"value": unique_speakers},
        "longest_rep_turn_seconds": {
            "value": round(max(rep_turns) / 1000, 1) if rep_turns else 0
        },
        "longest_buyer_turn_seconds": {
            "value": round(max(buyer_turns) / 1000, 1) if buyer_turns else 0
        },
        "segment_count": {"value": len(seg_list)},
    }

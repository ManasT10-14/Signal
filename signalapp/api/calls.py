"""
Calls API router — /api/v1/calls
"""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel

from signalapp.app.dependencies import CallRepo, TranscriptRepo, CurrentUserID
from signalapp.db.models import Call

router = APIRouter()


class CallResponse(BaseModel):
    id: str
    org_id: str
    rep_name: str
    call_type: str
    deal_name: str | None
    call_date: str | None
    duration_seconds: int | None
    processing_status: str
    created_at: str

    class Config:
        from_attributes = True


class CallListResponse(BaseModel):
    calls: list[CallResponse]
    total: int


class TranscriptSegmentResponse(BaseModel):
    segment_id: str
    index: int
    speaker: str
    role: str
    start_ms: int
    end_ms: int
    text: str
    coaching: dict | None = None  # Per-segment coaching annotation (if available)


class UploadResponse(BaseModel):
    call_id: str
    status: str
    message: str


class PasteTranscriptRequest(BaseModel):
    rep_name: str
    call_type: str
    deal_name: str | None = None
    transcript_text: str
    call_date: str | None = None


class PasteTranscriptResponse(BaseModel):
    call_id: str
    status: str
    segments_count: int


@router.get("/", response_model=CallListResponse)
async def list_calls(
    user_id: CurrentUserID,
    call_repo: CallRepo,
    limit: int = 50,
    offset: int = 0,
    rep_name: str | None = None,
    processing_status: str | None = None,
) -> CallListResponse:
    """
    List calls for the current user's organization.
    Phase 2: Filter by org_id from JWT.
    """
    # TODO: Get org_id from user context
    # For now, use a placeholder org
    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    calls = await call_repo.list_by_org(
        org_id=org_id,
        limit=limit,
        offset=offset,
        rep_name=rep_name,
        processing_status=processing_status,
    )

    return CallListResponse(
        calls=[
            CallResponse(
                id=str(c.id),
                org_id=str(c.org_id),
                rep_name=c.rep_name,
                call_type=c.call_type,
                deal_name=c.deal_name,
                call_date=c.call_date.isoformat() if c.call_date else None,
                duration_seconds=c.duration_seconds,
                processing_status=c.processing_status,
                created_at=c.created_at.isoformat(),
            )
            for c in calls
        ],
        total=len(calls),
    )


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: str,
    user_id: CurrentUserID,
    call_repo: CallRepo,
) -> CallResponse:
    """Get a single call by ID."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid call_id format")

    call = await call_repo.get_by_id(call_uuid)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    return CallResponse(
        id=str(call.id),
        org_id=str(call.org_id),
        rep_name=call.rep_name,
        call_type=call.call_type,
        deal_name=call.deal_name,
        call_date=call.call_date.isoformat() if call.call_date else None,
        duration_seconds=call.duration_seconds,
        processing_status=call.processing_status,
        created_at=call.created_at.isoformat(),
    )


@router.get("/{call_id}/transcript", response_model=list[TranscriptSegmentResponse])
async def get_call_transcript(
    call_id: str,
    user_id: CurrentUserID,
    call_repo: CallRepo,
) -> list[dict]:
    """Return all transcript segments for a call, ordered by start time."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid call_id format")

    call = await call_repo.get_by_id(call_uuid)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.transcript or not call.transcript.segments:
        return []

    # Get segment coaching from latest analysis run
    coaching_by_index = {}
    if call.analysis_runs:
        latest_run = sorted(call.analysis_runs, key=lambda r: r.run_number, reverse=True)[0]
        if latest_run.segment_coaching and latest_run.segment_coaching.get("annotations"):
            for ann in latest_run.segment_coaching["annotations"]:
                idx = ann.get("segment_index")
                if idx is not None:
                    coaching_by_index[idx] = ann

    return sorted([
        {
            "segment_id": str(seg.id),
            "index": seg.segment_index,
            "speaker": seg.speaker_name,
            "role": seg.speaker_role,
            "start_ms": seg.start_time_ms,
            "end_ms": seg.end_time_ms,
            "text": seg.text_content,
            "coaching": coaching_by_index.get(seg.segment_index),
        }
        for seg in call.transcript.segments
    ], key=lambda s: s["start_ms"])


@router.get("/{call_id}/coaching-meta")
async def get_coaching_meta(
    call_id: str,
    user_id: CurrentUserID,
    call_repo: CallRepo,
) -> dict:
    """Return coaching metadata: grade, assessment, arc, stats."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid call_id format")

    call = await call_repo.get_by_id(call_uuid)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.analysis_runs:
        return {"available": False}

    latest_run = sorted(call.analysis_runs, key=lambda r: r.run_number, reverse=True)[0]
    sc = latest_run.segment_coaching or {}

    return {
        "available": bool(sc),
        "rep_grade": sc.get("rep_grade", ""),
        "overall_assessment": sc.get("overall_assessment", ""),
        "conversation_arc": sc.get("conversation_arc", ""),
        "strongest_skill": sc.get("strongest_skill", ""),
        "biggest_growth_area": sc.get("biggest_growth_area", ""),
        "total_coaching_moments": sc.get("total_coaching_moments", 0),
        "total_signal_moments": sc.get("total_signal_moments", 0),
        "total_wins": sc.get("total_wins", 0),
        "turning_point_segment": sc.get("turning_point_segment", -1),
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_call(
    user_id: CurrentUserID,
    call_repo: CallRepo,
    audio_file: UploadFile | None = File(None),
    rep_name: str = Form(...),
    call_type: str = Form(...),
    deal_name: str | None = Form(None),
    call_date: str | None = Form(None),
    notes: str | None = Form(None),
) -> UploadResponse:
    """
    Upload endpoint — DISABLED in transcript-only mode.
    Use POST /api/v1/calls/paste-transcript instead.
    """
    raise HTTPException(
        status_code=410,
        detail="Audio upload disabled. Use POST /api/v1/calls/paste-transcript with transcript text.",
    )


@router.post("/paste-transcript", response_model=PasteTranscriptResponse)
async def paste_transcript(
    request: PasteTranscriptRequest,
    user_id: CurrentUserID,
) -> PasteTranscriptResponse:
    """
    Primary Phase 1 input method: paste transcript directly.
    Stores transcript text in Postgres, skips ASR entirely.
    """
    from signalapp.db.repository import get_session
    from signalapp.db.models import Call as CallModel, Transcript as TranscriptModel, TranscriptSegment as SegmentModel
    from signalapp.jobs.pipeline import run_pipeline_job

    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    parsed_date = None
    if request.call_date:
        try:
            parsed_date = datetime.fromisoformat(request.call_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    segments = _parse_transcript(request.transcript_text)
    call_id: uuid.UUID
    transcript_id: uuid.UUID

    # Single session — all DB ops in one transaction, committed on exit
    async for session in get_session():
        call = CallModel(
            org_id=org_id, uploaded_by=user_id, rep_name=request.rep_name,
            call_type=request.call_type, deal_name=request.deal_name,
            call_date=parsed_date, input_type="paste",
        )
        session.add(call)
        await session.flush()
        call_id = call.id

        transcript = TranscriptModel(
            call_id=call_id, full_text=request.transcript_text,
            asr_provider="paste", asr_model=None, asr_confidence=1.0, language="en",
        )
        session.add(transcript)
        await session.flush()
        transcript_id = transcript.id

        seg_models = [
            SegmentModel(
                transcript_id=transcript_id, segment_index=s["segment_index"],
                speaker_name=s["speaker_name"], speaker_role=s.get("speaker_role", "unknown"),
                start_time_ms=s["start_time_ms"], end_time_ms=s["end_time_ms"],
                text_content=s["text"],
                word_count=s.get("word_count", len(s.get("text", "").split())),
            )
            for s in segments
        ]
        session.add_all(seg_models)
        await session.flush()
        # get_session commits on exit

    # Fire pipeline in background via memory queue thread pool.
    # Runs in ThreadPoolExecutor so blocking LLM I/O never blocks FastAPI's async loop.
    import logging
    logger = logging.getLogger(__name__)
    from signalapp.jobs.memory import get_memory_queue
    queue = get_memory_queue()
    job_id = await queue.enqueue_job("run_pipeline_job", call_id=str(call_id))
    logger.info(f"Enqueued pipeline job {job_id} for call {call_id}")

    return PasteTranscriptResponse(
        call_id=str(call_id),
        status="processing",
        segments_count=len(segments),
    )


def _parse_transcript(text: str) -> list[dict]:
    """
    Parse pasted transcript text into segments.

    Supports formats:
    - `[MM:SS] Speaker (role): text`
    - `[MM:SS] Speaker: text`
    - `Speaker (role): text` (no timestamp)
    - `Speaker: text` (no timestamp, role inferred)

    Handles:
    - Multiple [MM:SS] entries on a single line (pre-splits)
    - Continuation lines without timestamps (joins to previous speaker)
    """
    # Step 1: Join continuation lines to their parent speaker line.
    # A "continuation" is any line that doesn't start with [MM:SS] or Speaker:
    raw_lines = text.strip().split("\n")
    joined_lines = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        # Is this a new speaker turn? Check for [MM:SS] or "Name:" pattern
        is_new_turn = bool(
            re.match(r'\[\d{1,3}:\s*\d{2}\]', line)
            or re.match(r'[A-Za-z][\w\s]{0,30}\s*(?:\([^)]+\))?\s*:', line)
        )
        if is_new_turn or not joined_lines:
            joined_lines.append(line)
        else:
            # Continuation of previous speaker — append
            joined_lines[-1] += " " + line

    # Step 2: Pre-split lines that contain multiple [MM:SS] entries
    expanded_lines = []
    for line in joined_lines:
        parts = re.split(r'(?=\[\d{1,3}:\s*\d{2}\])', line)
        for part in parts:
            part = part.strip()
            if part:
                expanded_lines.append(part)

    # Step 3: Parse each line into a segment
    segments = []
    for idx, line in enumerate(expanded_lines):
        # Try timestamped format: [MM:SS] Speaker (role): text
        ts_match = re.match(r"\[(\d+):\s*(\d+)\]\s*(.+?)\s*(?:\(([^)]+)\))?\s*:\s*(.*)", line)
        if ts_match:
            mins, secs, speaker, role, text_content = ts_match.groups()
            start_ms = int(mins) * 60 * 1000 + int(secs) * 1000
            role = _normalize_role(role)
        else:
            # Try simple format: Speaker: text
            simple_match = re.match(r"(.+?)\s*:\s*(.*)", line)
            if simple_match:
                speaker, text_content = simple_match.groups()
                start_ms = idx * 30000
                role = _infer_role(speaker)
            else:
                # Plain text — append to previous segment if possible
                if segments:
                    segments[-1]["text"] += " " + line
                    segments[-1]["word_count"] = len(segments[-1]["text"].split())
                    continue
                speaker = "Unknown"
                text_content = line
                start_ms = idx * 30000
                role = "unknown"

        text_content = text_content.strip()
        word_count = len(text_content.split())

        segments.append({
            "segment_index": idx,
            "speaker_name": speaker.strip(),
            "speaker_role": role,
            "start_time_ms": start_ms,
            "end_time_ms": start_ms + 30000,
            "text": text_content,
            "word_count": word_count,
        })

    # Step 4: Fix segment indices and end times
    for i, seg in enumerate(segments):
        seg["segment_index"] = i
    for i in range(len(segments) - 1):
        segments[i]["end_time_ms"] = segments[i + 1]["start_time_ms"]

    return segments


@router.get("/{call_id}/metrics")
async def get_call_metrics(
    call_id: str,
    user_id: CurrentUserID,
    call_repo: CallRepo,
) -> dict:
    """Return base metrics for a call (talk ratio, WPM, questions, etc.)."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid call_id format")

    call = await call_repo.get_by_id(call_uuid)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    # Get latest analysis run's summary which contains base_metrics
    from signalapp.db.repository import AnalysisRunRepository
    run_repo = AnalysisRunRepository()
    latest_run = await run_repo.get_latest_for_call(call_uuid)

    if latest_run and latest_run.settings_snapshot:
        metrics = latest_run.settings_snapshot.get("base_metrics", {})
    else:
        metrics = {}

    # If no stored metrics, compute from segments
    if not metrics and call.transcript and call.transcript.segments:
        from signalapp.pipeline.nodes.base_metrics import base_metrics_node
        segments = [
            {
                "segment_id": str(s.id),
                "speaker_name": s.speaker_name,
                "speaker_role": s.speaker_role,
                "start_time_ms": s.start_time_ms,
                "end_time_ms": s.end_time_ms,
                "text": s.text_content,
                "word_count": s.word_count,
            }
            for s in call.transcript.segments
        ]
        result = await base_metrics_node({"transcript_segments": segments})
        metrics = result.get("base_metrics", {})

    return {"call_id": call_id, "metrics": metrics}


@router.post("/{call_id}/reanalyze")
async def reanalyze_call(
    call_id: str,
    user_id: CurrentUserID,
    call_repo: CallRepo,
) -> dict:
    """Re-run the analysis pipeline for an existing call."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid call_id format")

    call = await call_repo.get_by_id(call_uuid)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    # Update call status to processing
    await call_repo.update_status(call_uuid, "processing")

    # Enqueue pipeline job
    from signalapp.jobs.memory import get_memory_queue
    queue = get_memory_queue()
    job_id = await queue.enqueue_job("run_pipeline_job", call_id=str(call_uuid))

    import logging
    logging.getLogger(__name__).info(f"Re-analysis enqueued: job {job_id} for call {call_uuid}")

    return {"call_id": call_id, "status": "processing", "message": "Re-analysis started"}


def _normalize_role(role: str | None) -> str:
    """Normalize role string to rep/buyer/unknown."""
    if not role:
        return "unknown"
    role_lower = role.lower().strip()
    if role_lower in ("rep", "agent", "seller", "sales"):
        return "rep"
    if role_lower in ("buyer", "customer", "prospect"):
        return "buyer"
    return "unknown"


def _infer_role(speaker: str) -> str:
    """Infer speaker role from name patterns."""
    speaker_lower = speaker.lower()
    buyer_patterns = ("customer", "buyer", "prospect", "client")
    rep_patterns = ("rep", "agent", "seller", "sales", "mr.", "mrs.", "ms.")
    if any(p in speaker_lower for p in buyer_patterns):
        return "buyer"
    if any(p in speaker_lower for p in rep_patterns):
        return "rep"
    return "unknown"

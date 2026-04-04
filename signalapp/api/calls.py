"""
Calls API router — /api/v1/calls
"""
from __future__ import annotations

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
    call_repo: CallRepo,
    transcript_repo: TranscriptRepo,
) -> PasteTranscriptResponse:
    """
    Primary Phase 1 input method: paste transcript directly.
    Stores transcript text in Postgres, skips ASR entirely.
    """
    from signalapp.jobs.pipeline import run_pipeline_job

    # TODO: Get org_id from user context
    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Parse call date
    parsed_date = None
    if request.call_date:
        try:
            parsed_date = datetime.fromisoformat(request.call_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Create call record
    call = await call_repo.create(
        org_id=org_id,
        uploaded_by=user_id,
        rep_name=request.rep_name,
        call_type=request.call_type,
        deal_name=request.deal_name,
        call_date=parsed_date,
        input_type="paste",
    )

    # Parse and segment the transcript
    segments = _parse_transcript(request.transcript_text)

    # Create transcript record
    transcript = await transcript_repo.create(
        call_id=call.id,
        full_text=request.transcript_text,
        asr_provider="paste",
        asr_model=None,
        asr_confidence=1.0,
        language="en",
    )

    # Store segments
    await transcript_repo.add_segments(
        transcript_id=transcript.id,
        segments=segments,
    )

    # Enqueue pipeline job (runs in-process for memory mode)
    pipeline_error = None
    try:
        await run_pipeline_job({}, str(call.id))
    except Exception as e:
        pipeline_error = str(e)
        import logging
        logging.getLogger(__name__).exception(f"Pipeline job failed for call {call.id}: {e}")

    return PasteTranscriptResponse(
        call_id=str(call.id),
        status="failed" if pipeline_error else "processing",
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

    Returns list of segment dicts with:
    - segment_index: int
    - speaker_name: str
    - speaker_role: str ("rep" | "buyer" | "unknown")
    - start_time_ms: int
    - end_time_ms: int (estimated as start + 30 seconds)
    - text: str
    """
    segments = []
    lines = text.strip().split("\n")

    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Try timestamped format: [MM:SS] Speaker (role): text
        ts_match = re.match(r"\[(\d+):(\d+)\]\s*(.+?)\s*(?:\(([^)]+)\))?\s*:\s*(.*)", line)
        if ts_match:
            mins, secs, speaker, role, text_content = ts_match.groups()
            start_ms = int(mins) * 60 * 1000 + int(secs) * 1000
            role = _normalize_role(role)
        else:
            # Try simple format: Speaker: text
            simple_match = re.match(r"(.+?)\s*:\s*(.*)", line)
            if simple_match:
                speaker, text_content = simple_match.groups()
                start_ms = idx * 30000  # Estimate 30s per line
                role = _infer_role(speaker)
            else:
                # Plain text — treat as unknown speaker
                speaker = "Unknown"
                text_content = line
                start_ms = idx * 30000
                role = "unknown"

        # Estimate end time as start + 30 seconds
        end_ms = start_ms + 30000

        segments.append({
            "segment_index": idx,
            "speaker_name": speaker.strip(),
            "speaker_role": role,
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
            "text": text_content.strip(),
        })

    return segments


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

"""
Pipeline job — enqueued to start the LangGraph workflow.
Works with both ARQ+Redis and the in-memory queue (QUEUE_MODE=memory).
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


async def run_pipeline_job(ctx: dict, call_id: str, force_reanalyze: bool = False) -> dict:
    """
    LangGraph pipeline job.

    1. Load call + segments from DB
    2. Build initial state
    3. Run LangGraph workflow (store_results_node handles all DB persistence)
    """
    from signalapp.pipeline.pipeline import create_pipeline_workflow
    from signalapp.db.repository import (
        CallRepository,
        TranscriptRepository,
        get_session,
    )

    call_uuid = uuid.UUID(call_id)

    try:
        async for session in get_session():
            call_repo = CallRepository()
            transcript_repo = TranscriptRepository()

            call = await call_repo.get_by_id(call_uuid)
            if call is None:
                return {"status": "error", "error": f"Call {call_id} not found"}

            segments = await transcript_repo.get_segments_for_call(call_uuid)
            if not segments:
                return {"status": "error", "error": f"No segments for call {call_id}"}

            # Build state
            state = {
                "call_id": call_id,
                "call_type": call.call_type,
                "transcript_segments": [
                    {
                        "segment_id": str(s.id),
                        "segment_index": s.segment_index,
                        "speaker_name": s.speaker_name,
                        "speaker_role": s.speaker_role,
                        "start_time_ms": s.start_time_ms,
                        "end_time_ms": s.end_time_ms,
                        "text": s.text_content,
                        "word_count": s.word_count,
                    }
                    for s in segments
                ],
            }

        # Run pipeline with global timeout to prevent blocking the backend
        import asyncio
        app = create_pipeline_workflow()
        try:
            final_state = await asyncio.wait_for(app.ainvoke(state), timeout=300)  # 5 min max
        except asyncio.TimeoutError:
            logger.error(f"[pipeline] Pipeline timed out for {call_id} after 300s")
            from signalapp.db.repository import CallRepository as CR
            await CR().update_status(call_uuid, "ready")
            return {"status": "error", "error": "Pipeline timed out"}

        store_status = final_state.get("store_status", "unknown")
        if store_status == "error":
            logger.error(f"[pipeline] Store node failed for {call_id}: {final_state.get('errors')}")

        return {
            "status": "complete" if store_status == "success" else "error",
            "call_id": call_id,
            "active_frameworks": list(final_state.get("active_frameworks", [])),
            "insight_count": len(final_state.get("verified_insights", [])),
        }

    except Exception as e:
        logger.exception(f"[pipeline] Failed for {call_id}: {e}")
        # Try to mark call as failed
        try:
            from signalapp.db.repository import CallRepository as CR
            cr = CR()
            await cr.update_status(call_uuid, "failed")
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


# Register with memory queue if in use
from signalapp.jobs.memory import register_job
run_pipeline_job = register_job(run_pipeline_job)

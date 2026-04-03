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
    3. Run LangGraph workflow
    4. Store results to DB
    """
    from signalapp.pipeline.pipeline import create_pipeline_workflow
    from signalapp.db.repository import (
        CallRepository,
        TranscriptRepository,
        AnalysisRunRepository,
        Pass1ResultRepository,
        FrameworkResultRepository,
        InsightRepository,
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

        # Run pipeline
        app = create_pipeline_workflow()
        final_state = await app.ainvoke(state)

        # Store results
        await _store_results(call_uuid, final_state)

        return {
            "status": "complete",
            "call_id": call_id,
            "active_frameworks": list(final_state.get("active_frameworks", [])),
            "insight_count": len(final_state.get("verified_insights", [])),
        }

    except Exception as e:
        logger.exception(f"[pipeline] Failed for {call_id}: {e}")
        return {"status": "error", "error": str(e)}


async def _store_results(call_uuid: uuid.UUID, state: dict) -> None:
    """Persist pipeline outputs to DB."""
    from signalapp.db.repository import (
        AnalysisRunRepository,
        Pass1ResultRepository,
        FrameworkResultRepository,
        InsightRepository,
        CallRepository,
        get_session,
    )

    async for session in get_session():
        run_repo = AnalysisRunRepository()
        pass1_repo = Pass1ResultRepository()
        fw_repo = FrameworkResultRepository()
        insight_repo = InsightRepository()
        call_repo = CallRepository()

        # Create analysis run
        run = await run_repo.create(call_id=call_uuid)

        # Store Pass1 result
        pass1_result = state.get("pass1_result")
        if pass1_result:
            await pass1_repo.create(
                analysis_run_id=run.id,
                hedge_data=pass1_result.get("hedge_data", []),
                sentiment_data=pass1_result.get("sentiment_data", []),
                appraisal_data=pass1_result.get("appraisal_data", []),
                prompt_version=pass1_result.get("prompt_version", "v1"),
                model_used=pass1_result.get("model_used", "gemini"),
                model_version=pass1_result.get("model_version", ""),
                tokens_input=pass1_result.get("tokens_input", 0),
                tokens_output=pass1_result.get("tokens_output", 0),
                latency_ms=pass1_result.get("latency_ms", 0),
                cost_usd=pass1_result.get("cost_usd", 0.0),
            )

        # Store framework results
        fw_results = state.get("framework_results", {})
        for fw_id, fw_dict in fw_results.items():
            if isinstance(fw_dict, dict):
                await fw_repo.create(
                    analysis_run_id=run.id,
                    framework_id=f"FW-{fw_id:02d}",
                    framework_version="v1",
                    prompt_version="v1",
                    model_used="gemini",
                    model_version="",
                    prompt_group=fw_dict.get("prompt_group", ""),
                    score=fw_dict.get("score"),
                    severity=fw_dict.get("severity", "green"),
                    confidence=fw_dict.get("confidence", 0.0),
                    headline=fw_dict.get("headline", ""),
                    explanation=fw_dict.get("explanation", ""),
                    coaching_recommendation=fw_dict.get("coaching_recommendation", ""),
                    evidence=fw_dict.get("evidence", []),
                    raw_output=fw_dict.get("raw_analysis", {}),
                )

        # Store insights
        insights = state.get("verified_insights", [])
        for insight_dict in insights:
            if isinstance(insight_dict, dict):
                await insight_repo.create(
                    call_id=call_uuid,
                    analysis_run_id=run.id,
                    framework_result_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),  # placeholder
                    priority_rank=insight_dict.get("priority_rank", 0),
                    is_top_insight=insight_dict.get("is_top_insight", False),
                    framework_name=insight_dict.get("framework_name", ""),
                    severity=insight_dict.get("severity", "green"),
                    confidence=insight_dict.get("confidence", 0.0),
                    headline=insight_dict.get("headline", ""),
                    explanation=insight_dict.get("explanation", ""),
                    evidence=insight_dict.get("evidence", []),
                    coaching_recommendation=insight_dict.get("coaching_recommendation", ""),
                )

        await run_repo.complete(run.id, status="complete")
        await call_repo.update_status(call_uuid, "ready")

        logger.info(f"[pipeline] Stored results for call {call_uuid}")


# Register with memory queue if in use
from signalapp.jobs.memory import register_job
run_pipeline_job = register_job(run_pipeline_job)

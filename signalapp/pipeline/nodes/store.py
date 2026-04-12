"""
Store results node — persists pipeline outputs to the database.

Uses a single session_scope to ensure all writes happen in one transaction.
This is the final node before END.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from signalapp.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


async def store_results_node(state: PipelineState) -> dict:
    """
    Store all pipeline results to the database in a single transaction.
    """
    from signalapp.db.repository import session_scope
    from signalapp.db.models import (
        AnalysisRun, Pass1Result, FrameworkResult, Insight, Call,
    )
    from signalapp.domain.framework import normalize_severity
    from sqlalchemy import update, select, func

    call_id_str = state["call_id"]
    pass1_result = state.get("pass1_result") or {}
    framework_results = state.get("framework_results") or {}
    verified_insights = state.get("verified_insights") or []
    summary = state.get("summary")
    base_metrics = state.get("base_metrics")
    routing_decisions = state.get("routing_decisions") or []

    try:
        if isinstance(call_id_str, str):
            call_id = uuid.UUID(call_id_str)
        else:
            call_id = call_id_str

        # Single transaction for all DB writes
        async with session_scope() as session:
            # 1. Create AnalysisRun
            run_count_result = await session.execute(
                select(func.count(AnalysisRun.id)).where(AnalysisRun.call_id == call_id)
            )
            run_count = run_count_result.scalar() or 0

            settings_snapshot = {
                "routing_decisions": [
                    {"fw_id": d.get("fw_id"), "decision": d.get("decision"), "reason": d.get("reason")}
                    for d in routing_decisions
                ] if routing_decisions else [],
                "groups_run": list(framework_results.keys()) if framework_results else [],
            }
            if base_metrics:
                settings_snapshot["base_metrics"] = base_metrics

            segment_coaching_data = state.get("segment_coaching")

            run = AnalysisRun(
                call_id=call_id,
                run_number=run_count + 1,
                settings_snapshot=settings_snapshot,
                summary=summary,
                segment_coaching=segment_coaching_data,
            )
            session.add(run)
            await session.flush()
            await session.refresh(run)
            analysis_run_id = run.id
            logger.info(f"[store] Created AnalysisRun {analysis_run_id} for call {call_id}")

            # 2. Store Pass1Result
            if pass1_result:
                p1 = Pass1Result(
                    analysis_run_id=analysis_run_id,
                    hedge_data=pass1_result.get("hedge_data", []),
                    sentiment_data=pass1_result.get("sentiment_data", []),
                    appraisal_data=pass1_result.get("appraisal_data", []),
                    prompt_version=pass1_result.get("prompt_version", "v1"),
                    model_used=pass1_result.get("model_used", "gemini"),
                    model_version=pass1_result.get("model_version", "unknown"),
                    tokens_input=pass1_result.get("tokens_input", 0),
                    tokens_output=pass1_result.get("tokens_output", 0),
                    latency_ms=pass1_result.get("latency_ms", 0),
                    cost_usd=pass1_result.get("cost_usd", 0.0),
                )
                session.add(p1)
                await session.flush()

            # 3. Store FrameworkResults
            fw_uuid_by_id: dict[str, uuid.UUID] = {}
            for fw_id, result_dict in framework_results.items():
                framework_id_str = result_dict.get("framework_id", f"FW-{fw_id:02d}")
                severity = normalize_severity(result_dict.get("severity", "yellow"))
                prompt_group = _get_group_for_framework(fw_id)

                fw = FrameworkResult(
                    analysis_run_id=analysis_run_id,
                    framework_id=framework_id_str,
                    framework_version="v1",
                    prompt_version="v1",
                    model_used="gemini",
                    model_version="unknown",
                    prompt_group=prompt_group,
                    score=result_dict.get("score"),
                    severity=severity,
                    confidence=result_dict.get("confidence", 0.5),
                    headline=result_dict.get("headline", f"Framework {fw_id}"),
                    explanation=result_dict.get("explanation", ""),
                    coaching_recommendation=result_dict.get("coaching_recommendation", ""),
                    evidence=result_dict.get("evidence", []),
                    raw_output=result_dict.get("raw_analysis", {}),
                )
                session.add(fw)
                await session.flush()
                await session.refresh(fw)
                fw_uuid_by_id[framework_id_str] = fw.id

            logger.info(f"[store] Stored {len(fw_uuid_by_id)} FrameworkResults for call {call_id}")

            # 4. Store Insights
            insight_count = 0
            for insight in verified_insights:
                framework_result_id_str = insight.get("framework_result_id", "")
                fw_uuid = fw_uuid_by_id.get(framework_result_id_str)
                if fw_uuid is None:
                    try:
                        fw_num_int = int(framework_result_id_str.replace("FW-", ""))
                        fw_uuid = fw_uuid_by_id.get(f"FW-{fw_num_int:02d}")
                    except ValueError:
                        pass
                if fw_uuid is None:
                    logger.warning(f"[store] No FrameworkResult UUID for {framework_result_id_str}, skipping")
                    continue

                ins = Insight(
                    call_id=call_id,
                    analysis_run_id=analysis_run_id,
                    framework_result_id=fw_uuid,
                    priority_rank=insight.get("priority_rank", 0),
                    is_top_insight=insight.get("is_top_insight", False),
                    framework_name=insight.get("framework_name", ""),
                    severity=normalize_severity(insight.get("severity", "green")),
                    confidence=insight.get("confidence", 0.0),
                    headline=insight.get("headline", ""),
                    explanation=insight.get("explanation", ""),
                    evidence=insight.get("evidence", []),
                    coaching_recommendation=insight.get("coaching_recommendation", ""),
                )
                session.add(ins)
                insight_count += 1

            await session.flush()
            logger.info(f"[store] Stored {insight_count} Insights for call {call_id}")

            # 5. Mark run complete and update call status
            run.status = "complete"
            run.completed_at = datetime.utcnow()
            await session.execute(
                update(Call).where(Call.id == call_id).values(processing_status="ready")
            )

            # Commit everything in one transaction
            await session.commit()
            logger.info(f"[store] All results committed for call {call_id}")

        return {
            "store_status": "success",
            "call_id": call_id_str,
            "analysis_run_id": str(analysis_run_id),
            "frameworks_stored": len(fw_uuid_by_id),
            "insights_stored": insight_count,
            "summary_generated": summary is not None,
        }

    except Exception as e:
        logger.error(f"[store] Failed for call {call_id_str}: {e}", exc_info=True)
        # Still try to mark call as ready so UI doesn't hang
        try:
            from signalapp.db.repository import CallRepository
            cr = CallRepository()
            await cr.update_status(uuid.UUID(call_id_str) if isinstance(call_id_str, str) else call_id_str, "ready")
        except Exception:
            pass
        return {
            "store_status": "error",
            "call_id": call_id_str,
            "errors": [f"Store failed: {str(e)}"],
        }


def _get_group_for_framework(fw_id: int) -> str:
    from signalapp.domain.routing import GROUP_MEMBERSHIP
    for group_id, members in GROUP_MEMBERSHIP.items():
        if fw_id in members:
            return group_id
    return "B"

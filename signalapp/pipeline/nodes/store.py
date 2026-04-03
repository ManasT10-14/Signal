"""
Store results node — persists pipeline outputs to the database.

Writes: AnalysisRun, Pass1Result, FrameworkResults, Insights.
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
    Store all pipeline results to the database.

    Inputs: call_id, pass1_result, framework_results, verified_insights, summary
    Outputs: stored call_id confirmation

    Uses the repository pattern for all DB operations.
    """
    from signalapp.db.repository import (
        AnalysisRunRepository,
        Pass1ResultRepository,
        FrameworkResultRepository,
        InsightRepository,
        CallRepository,
    )
    from signalapp.db.models import AnalysisRun, FrameworkResult
    from sqlalchemy import select

    call_id_str = state["call_id"]
    pass1_result = state.get("pass1_result") or {}
    framework_results = state.get("framework_results") or {}
    verified_insights = state.get("verified_insights") or []
    summary = state.get("summary")
    routing_decisions = state.get("routing_decisions") or []

    try:
        # Convert call_id to UUID if it's a string
        if isinstance(call_id_str, str):
            try:
                call_id = uuid.UUID(call_id_str)
            except ValueError:
                call_id = uuid.uuid4()  # Generate new UUID if invalid
        else:
            call_id = call_id_str

        # Create AnalysisRun
        analysis_run_repo = AnalysisRunRepository()
        settings_snapshot = {
            "routing_decisions": [
                {"fw_id": d.get("fw_id"), "decision": d.get("decision"), "reason": d.get("reason")}
                for d in routing_decisions
            ] if routing_decisions else [],
            "groups_run": list(framework_results.keys()) if framework_results else [],
        }
        analysis_run = await analysis_run_repo.create(
            call_id=call_id,
            settings_snapshot=settings_snapshot,
        )
        analysis_run_id = analysis_run.id
        logger.info(f"[store] Created AnalysisRun {analysis_run_id} for call {call_id}")

        # Store Pass1Result
        if pass1_result:
            pass1_repo = Pass1ResultRepository()
            await pass1_repo.create(
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
            logger.info(f"[store] Stored Pass1Result for call {call_id}")

        # Store FrameworkResults and track UUIDs by framework_id string
        fw_uuid_by_id: dict[str, uuid.UUID] = {}
        fw_result_repo = FrameworkResultRepository()

        for fw_id, result_dict in framework_results.items():
            # fw_id is an int like 1, 2, 3
            # framework_id in result is like "FW-01", "FW-02"
            framework_id_str = result_dict.get("framework_id", f"FW-{fw_id:02d}")

            # Get framework metadata from result or use defaults
            severity = result_dict.get("severity", "yellow")
            if hasattr(severity, "value"):
                severity = severity.value
            severity = str(severity)

            score = result_dict.get("score")
            confidence = result_dict.get("confidence", 0.5)
            headline = result_dict.get("headline", f"Framework {fw_id}")
            explanation = result_dict.get("explanation", "")
            coaching = result_dict.get("coaching_recommendation", "")
            evidence = result_dict.get("evidence", [])
            raw_output = result_dict.get("raw_analysis", {})

            # Get group from framework_id
            prompt_group = _get_group_for_framework(fw_id)

            fw_result = await fw_result_repo.create(
                analysis_run_id=analysis_run_id,
                framework_id=framework_id_str,
                framework_version="v1",
                prompt_version="v1",
                model_used="gemini",
                model_version="unknown",
                prompt_group=prompt_group,
                score=score,
                severity=severity,
                confidence=confidence,
                headline=headline,
                explanation=explanation,
                coaching_recommendation=coaching,
                evidence=evidence,
                raw_output=raw_output,
            )
            fw_uuid_by_id[framework_id_str] = fw_result.id

        logger.info(f"[store] Stored {len(fw_uuid_by_id)} FrameworkResults for call {call_id}")

        # Store Insights
        if verified_insights:
            insight_repo = InsightRepository()

            # Prepare bulk insight data
            insight_data = []
            for insight in verified_insights:
                framework_result_id_str = insight.get("framework_result_id", "")

                # Find the UUID for this framework result
                fw_uuid = fw_uuid_by_id.get(framework_result_id_str)

                if fw_uuid is None:
                    # Fallback: try to find by framework number
                    fw_num = framework_result_id_str.replace("FW-", "").lstrip("0")
                    fallback_key = f"FW-{int(fw_num):02d}" if fw_num.isdigit() else framework_result_id_str
                    fw_uuid = fw_uuid_by_id.get(fallback_key)

                if fw_uuid is None:
                    logger.warning(f"[store] Could not find FrameworkResult UUID for {framework_result_id_str}, skipping insight")
                    continue

                # Handle severity
                sev = insight.get("severity", "green")
                if hasattr(sev, "value"):
                    sev = sev.value
                sev = str(sev)

                insight_data.append({
                    "call_id": call_id,
                    "analysis_run_id": analysis_run_id,
                    "framework_result_id": fw_uuid,
                    "priority_rank": insight.get("priority_rank", 0),
                    "is_top_insight": insight.get("is_top_insight", False),
                    "framework_name": insight.get("framework_name", ""),
                    "severity": sev,
                    "confidence": insight.get("confidence", 0.0),
                    "headline": insight.get("headline", ""),
                    "explanation": insight.get("explanation", ""),
                    "evidence": insight.get("evidence", []),
                    "coaching_recommendation": insight.get("coaching_recommendation", ""),
                })

            if insight_data:
                await insight_repo.bulk_create(insight_data)
                logger.info(f"[store] Stored {len(insight_data)} Insights for call {call_id}")

        # Mark AnalysisRun as complete
        await analysis_run_repo.complete(analysis_run_id, status="complete")

        # Update call status to ready
        call_repo = CallRepository()
        await call_repo.update_status(call_id, "ready")

        return {
            "store_status": "success",
            "call_id": call_id_str,
            "analysis_run_id": str(analysis_run_id),
            "frameworks_stored": len(fw_uuid_by_id),
            "insights_stored": len(verified_insights),
            "summary_generated": summary is not None,
        }

    except Exception as e:
        logger.error(f"[store] Failed to store results for call {call_id_str}: {e}")
        return {
            "store_status": "error",
            "call_id": call_id_str,
            "errors": [f"Store failed: {str(e)}"],
        }


def _get_group_for_framework(fw_id: int) -> str:
    """Get the prompt group for a framework ID."""
    from signalapp.domain.routing import GROUP_MEMBERSHIP

    for group_id, members in GROUP_MEMBERSHIP.items():
        if fw_id in members:
            return group_id
    return "B"  # Default to Group B


# ─── Repository imports (lazy to avoid circular imports) ────────────────────────


class AnalysisRunRepository:
    """Repository for AnalysisRun entity."""

    async def create(self, call_id: uuid.UUID, settings_snapshot: dict | None = None):
        from signalapp.db.models import AnalysisRun
        from signalapp.db.repository import get_session

        async for session in get_session():
            # Get next run number
            from sqlalchemy import select, func
            result = await session.execute(
                select(func.count(AnalysisRun.id)).where(AnalysisRun.call_id == call_id)
            )
            run_count = result.scalar() or 0

            run = AnalysisRun(
                call_id=call_id,
                run_number=run_count + 1,
                settings_snapshot=settings_snapshot or {},
            )
            session.add(run)
            await session.flush()
            await session.refresh(run)
            return run

    async def complete(self, run_id: uuid.UUID, status: str = "complete"):
        from signalapp.db.models import AnalysisRun
        from signalapp.db.repository import get_session
        from sqlalchemy import update

        async for session in get_session():
            await session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == run_id)
                .values(status=status, completed_at=datetime.utcnow())
            )


class Pass1ResultRepository:
    """Repository for Pass1Result."""

    async def create(
        self,
        analysis_run_id: uuid.UUID,
        hedge_data: list,
        sentiment_data: list,
        appraisal_data: list,
        prompt_version: str,
        model_used: str,
        model_version: str,
        tokens_input: int,
        tokens_output: int,
        latency_ms: int,
        cost_usd: float,
    ):
        from signalapp.db.models import Pass1Result
        from signalapp.db.repository import get_session

        async for session in get_session():
            result = Pass1Result(
                analysis_run_id=analysis_run_id,
                hedge_data=hedge_data,
                sentiment_data=sentiment_data,
                appraisal_data=appraisal_data,
                prompt_version=prompt_version,
                model_used=model_used,
                model_version=model_version,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )
            session.add(result)
            await session.flush()
            await session.refresh(result)
            return result


class FrameworkResultRepository:
    """Repository for FrameworkResult."""

    async def create(
        self,
        analysis_run_id: uuid.UUID,
        framework_id: str,
        framework_version: str,
        prompt_version: str,
        model_used: str,
        model_version: str,
        prompt_group: str,
        severity: str,
        confidence: float,
        headline: str,
        explanation: str,
        coaching_recommendation: str,
        score: float | None = None,
        evidence: list | None = None,
        raw_output: dict | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
    ):
        from signalapp.db.models import FrameworkResult
        from signalapp.db.repository import get_session

        async for session in get_session():
            result = FrameworkResult(
                analysis_run_id=analysis_run_id,
                framework_id=framework_id,
                framework_version=framework_version,
                prompt_version=prompt_version,
                model_used=model_used,
                model_version=model_version,
                prompt_group=prompt_group,
                score=score,
                severity=severity,
                confidence=confidence,
                headline=headline,
                explanation=explanation,
                evidence=evidence or [],
                coaching_recommendation=coaching_recommendation,
                raw_output=raw_output or {},
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )
            session.add(result)
            await session.flush()
            await session.refresh(result)
            return result


class InsightRepository:
    """Repository for Insight with all fields."""

    async def create(
        self,
        call_id: uuid.UUID,
        analysis_run_id: uuid.UUID,
        framework_result_id: uuid.UUID,
        priority_rank: int,
        is_top_insight: bool,
        framework_name: str,
        severity: str,
        confidence: float,
        headline: str,
        explanation: str,
        evidence: list,
        coaching_recommendation: str,
    ):
        from signalapp.db.models import Insight
        from signalapp.db.repository import get_session

        async for session in get_session():
            insight = Insight(
                call_id=call_id,
                analysis_run_id=analysis_run_id,
                framework_result_id=framework_result_id,
                priority_rank=priority_rank,
                is_top_insight=is_top_insight,
                framework_name=framework_name,
                severity=severity,
                confidence=confidence,
                headline=headline,
                explanation=explanation,
                evidence=evidence,
                coaching_recommendation=coaching_recommendation,
            )
            session.add(insight)
            await session.flush()
            await session.refresh(insight)
            return insight

    async def bulk_create(self, insights: list[dict]) -> list:
        from signalapp.db.models import Insight
        from signalapp.db.repository import get_session

        async for session in get_session():
            models = []
            for i in insights:
                insight = Insight(
                    call_id=i["call_id"],
                    analysis_run_id=i["analysis_run_id"],
                    framework_result_id=i["framework_result_id"],
                    priority_rank=i.get("priority_rank", 0),
                    is_top_insight=i.get("is_top_insight", False),
                    framework_name=i.get("framework_name", ""),
                    severity=i.get("severity", "yellow"),
                    confidence=i.get("confidence", 0.0),
                    headline=i.get("headline", ""),
                    explanation=i.get("explanation", ""),
                    evidence=i.get("evidence", []),
                    coaching_recommendation=i.get("coaching_recommendation", ""),
                )
                session.add(insight)
                models.append(insight)
            await session.flush()
            for model in models:
                await session.refresh(model)
            return models


class CallRepository:
    """Repository for Call entity."""

    async def update_status(self, call_id: uuid.UUID, status: str) -> None:
        from signalapp.db.models import Call
        from signalapp.db.repository import get_session
        from sqlalchemy import update

        async for session in get_session():
            await session.execute(
                update(Call).where(Call.id == call_id).values(processing_status=status)
            )

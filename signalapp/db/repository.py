"""
Repository pattern — database access layer.
All DB operations go through these repositories.
Uses async SQLAlchemy (asyncpg).
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import selectinload

from .models import (
    Base,
    Organization,
    User,
    Call,
    Transcript,
    TranscriptSegment,
    AnalysisRun,
    Pass1Result,
    FrameworkResult,
    Insight,
    BaseMetric,
    Setting,
)


# Global session factory — initialized by init_db()
_session_factory: sessionmaker | None = None
_db_url: str = ""


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite") or url.endswith(".db")


async def init_db(database_url: str | None = None) -> None:
    """
    Initialize the database engine and session factory.

    Uses config's db_url (SQLite for dev, Postgres for production)
    if no explicit URL is passed.
    """
    global _session_factory, _db_url
    from signalapp.app.config import get_config

    config = get_config()
    url = database_url or config.db_url
    _db_url = url

    # SQLite needs check_same_thread=False for aiosqlite
    engine_kwargs: dict = {"echo": False}
    if _is_sqlite(url):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(url, **engine_kwargs)
    _session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Get an async database session. Use as: async with get_session() as session:"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope():
    """Alternative context manager for explicit session handling."""
    async for session in get_session():
        yield session


# ─── Call Repository ────────────────────────────────────────────────────────────


class CallRepository:
    """Repository for Call entity."""

    async def create(
        self,
        org_id: uuid.UUID,
        uploaded_by: uuid.UUID,
        rep_name: str,
        call_type: str,
        deal_name: str | None = None,
        call_date: datetime | None = None,
        audio_s3_key: str | None = None,
        input_type: str = "audio",
    ) -> Call:
        """Create a new call record."""
        async for session in get_session():
            call = Call(
                org_id=org_id,
                uploaded_by=uploaded_by,
                rep_name=rep_name,
                call_type=call_type,
                deal_name=deal_name,
                call_date=call_date,
                audio_s3_key=audio_s3_key,
                input_type=input_type,
            )
            session.add(call)
            await session.flush()
            await session.refresh(call)
            return call

    async def get_by_id(self, call_id: uuid.UUID) -> Call | None:
        """Get a call by ID with all relationships."""
        async for session in get_session():
            result = await session.execute(
                select(Call)
                .options(
                    selectinload(Call.transcript).selectinload(Transcript.segments),
                    selectinload(Call.analysis_runs).selectinload(AnalysisRun.pass1_result),
                    selectinload(Call.analysis_runs).selectinload(AnalysisRun.framework_results),
                    selectinload(Call.insights),
                )
                .where(Call.id == call_id)
            )
            return result.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        rep_name: str | None = None,
        processing_status: str | None = None,
    ) -> list[Call]:
        """List calls for an org with optional filters."""
        async for session in get_session():
            query = select(Call).where(Call.org_id == org_id)
            if rep_name:
                query = query.where(Call.rep_name == rep_name)
            if processing_status:
                query = query.where(Call.processing_status == processing_status)
            query = query.order_by(Call.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_status(self, call_id: uuid.UUID, status: str) -> None:
        """Update call processing status."""
        async for session in get_session():
            await session.execute(
                update(Call).where(Call.id == call_id).values(processing_status=status)
            )


# ─── Transcript Repository ───────────────────────────────────────────────────────


class TranscriptRepository:
    """Repository for Transcript and TranscriptSegment entities."""

    async def create(
        self,
        call_id: uuid.UUID,
        full_text: str,
        asr_provider: str,
        asr_model: str | None = None,
        asr_confidence: float = 0.0,
        language: str = "en",
    ) -> Transcript:
        """Create a transcript for a call."""
        async for session in get_session():
            transcript = Transcript(
                call_id=call_id,
                full_text=full_text,
                asr_provider=asr_provider,
                asr_model=asr_model,
                asr_confidence=asr_confidence,
                language=language,
            )
            session.add(transcript)
            await session.flush()
            await session.refresh(transcript)
            return transcript

    async def add_segments(
        self,
        transcript_id: uuid.UUID,
        segments: list[dict],
    ) -> list[TranscriptSegment]:
        """Bulk insert transcript segments."""
        async for session in get_session():
            segment_models = [
                TranscriptSegment(
                    transcript_id=transcript_id,
                    segment_index=s["segment_index"],
                    speaker_name=s["speaker_name"],
                    speaker_role=s.get("speaker_role", "unknown"),
                    start_time_ms=s["start_time_ms"],
                    end_time_ms=s["end_time_ms"],
                    text_content=s["text"],
                    word_count=s.get("word_count", len(s.get("text", "").split())),
                )
                for s in segments
            ]
            session.add_all(segment_models)
            await session.flush()
            return segment_models

    async def get_segments_for_call(self, call_id: uuid.UUID) -> list[TranscriptSegment]:
        """Get all segments for a call, ordered by segment_index."""
        async for session in get_session():
            result = await session.execute(
                select(TranscriptSegment)
                .join(Transcript)
                .where(Transcript.call_id == call_id)
                .order_by(TranscriptSegment.segment_index)
            )
            return list(result.scalars().all())


# ─── AnalysisRun Repository ────────────────────────────────────────────────────


class AnalysisRunRepository:
    """Repository for AnalysisRun, Pass1Result, and FrameworkResult entities."""

    async def create(self, call_id: uuid.UUID, settings_snapshot: dict | None = None) -> AnalysisRun:
        """Create a new analysis run for a call."""
        async for session in get_session():
            # Get next run number
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

    async def get_by_id(self, run_id: uuid.UUID) -> AnalysisRun | None:
        """Get an analysis run by ID with all results."""
        async for session in get_session():
            result = await session.execute(
                select(AnalysisRun)
                .options(
                    selectinload(AnalysisRun.pass1_result),
                    selectinload(AnalysisRun.framework_results),
                    selectinload(AnalysisRun.insights),
                )
                .where(AnalysisRun.id == run_id)
            )
            return result.scalar_one_or_none()

    async def complete(self, run_id: uuid.UUID, status: str = "complete") -> None:
        """Mark an analysis run as complete."""
        async for session in get_session():
            await session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == run_id)
                .values(status=status, completed_at=datetime.utcnow())
            )


# ─── Pass1Result Repository ────────────────────────────────────────────────────


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
    ) -> Pass1Result:
        """Create a Pass1 result."""
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


# ─── FrameworkResult Repository ────────────────────────────────────────────────


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
    ) -> FrameworkResult:
        """Create a framework result."""
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


# ─── Insight Repository ────────────────────────────────────────────────────────


class InsightRepository:
    """Repository for Insight."""

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
    ) -> Insight:
        """Create an insight."""
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

    async def bulk_create(self, insights: list[dict]) -> list[Insight]:
        """Bulk create insights."""
        async for session in get_session():
            models = [Insight(**i) for i in insights]
            session.add_all(models)
            await session.flush()
            return models

    async def get_for_call(self, call_id: uuid.UUID, run_id: uuid.UUID | None = None) -> list[Insight]:
        """Get all insights for a call."""
        async for session in get_session():
            query = (
                select(Insight)
                .where(Insight.call_id == call_id)
                .order_by(Insight.priority_rank)
            )
            if run_id:
                query = query.where(Insight.analysis_run_id == run_id)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_feedback(
        self, insight_id: uuid.UUID, feedback: str, feedback_at: datetime | None = None
    ) -> Insight | None:
        """Update an insight's feedback with explicit session commit."""
        async with session_scope() as session:
            result = await session.execute(select(Insight).where(Insight.id == insight_id))
            insight = result.scalar_one_or_none()
            if insight is None:
                return None

            feedback_time = feedback_at or datetime.utcnow()
            await session.execute(
                update(Insight)
                .where(Insight.id == insight_id)
                .values(feedback=feedback, feedback_at=feedback_time)
            )
            await session.commit()
            await session.refresh(insight)

            # Return a detached copy with the updated values
            return Insight(
                id=insight.id,
                call_id=insight.call_id,
                analysis_run_id=insight.analysis_run_id,
                framework_result_id=insight.framework_result_id,
                priority_rank=insight.priority_rank,
                is_top_insight=insight.is_top_insight,
                framework_name=insight.framework_name,
                severity=insight.severity,
                confidence=insight.confidence,
                headline=insight.headline,
                explanation=insight.explanation,
                evidence=insight.evidence,
                coaching_recommendation=insight.coaching_recommendation,
                feedback=insight.feedback,
                feedback_at=insight.feedback_at,
                created_at=insight.created_at,
            )


# ─── BaseMetric Repository ─────────────────────────────────────────────────────


class BaseMetricRepository:
    """Repository for BaseMetric."""

    async def upsert(
        self,
        call_id: uuid.UUID,
        metric_name: str,
        metric_value: dict,
        computed_from: str = "transcript",
    ) -> BaseMetric:
        """Upsert a base metric for a call."""
        async for session in get_session():
            # Check if exists
            result = await session.execute(
                select(BaseMetric).where(
                    BaseMetric.call_id == call_id,
                    BaseMetric.metric_name == metric_name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                await session.execute(
                    update(BaseMetric)
                    .where(BaseMetric.id == existing.id)
                    .values(metric_value=metric_value)
                )
                existing.metric_value = metric_value
                return existing
            else:
                metric = BaseMetric(
                    call_id=call_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    computed_from=computed_from,
                )
                session.add(metric)
                await session.flush()
                await session.refresh(metric)
                return metric

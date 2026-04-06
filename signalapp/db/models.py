"""
SQLAlchemy models — the database schema for Signal.
Maps to the ERD in PRD Section 16.
Compatible with SQLAlchemy 1.4+ and both PostgreSQL and SQLite.
"""
from __future__ import annotations

import json
import uuid as uuid_lib
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    TypeDecorator,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


# ─── Cross-Dialect Type Helpers ────────────────────────────────────────────────


class GUID(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses PostgreSQL's UUID type when available, otherwise stores as String(36).
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid_lib.UUID):
            return value
        return uuid_lib.UUID(value)


class JSONB(TypeDecorator):
    """
    Platform-independent JSONB type.
    Uses PostgreSQL's JSONB when available, otherwise plain JSON.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name != "postgresql":
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name != "postgresql" and isinstance(value, str):
            return json.loads(value)
        return value


class Organization(Base):
    __tablename__ = "organization"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    name = Column(String(255), nullable=False)
    settings_json = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    calls = relationship("Call", back_populates="organization")


class User(Base):
    __tablename__ = "user"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    org_id = Column(GUID(), ForeignKey("organization.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(20), default="rep")  # admin|manager|rep|revops
    settings_json = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")
    calls = relationship("Call", back_populates="uploader")
    settings = relationship("Setting", back_populates="user")


class Call(Base):
    __tablename__ = "call"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    org_id = Column(GUID(), ForeignKey("organization.id"), nullable=False)
    uploaded_by = Column(GUID(), ForeignKey("user.id"), nullable=False)
    rep_name = Column(String(255), nullable=False)  # free text, not FK
    call_type = Column(String(20), nullable=False)  # discovery|demo|pricing|negotiation|close|checkin|other
    deal_name = Column(String(255), nullable=True)
    call_date = Column(Date, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    audio_s3_key = Column(String(512), nullable=True)
    input_type = Column(String(10), default="audio")  # audio|paste
    processing_status = Column(String(20), default="processing")  # processing|ready|failed|partial
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="calls")
    uploader = relationship("User", back_populates="calls")
    transcript = relationship("Transcript", back_populates="call", uselist=False)
    analysis_runs = relationship("AnalysisRun", back_populates="call")
    insights = relationship("Insight", back_populates="call")
    base_metrics = relationship("BaseMetric", back_populates="call")

    __table_args__ = (
        Index("ix_call_org_created", "org_id", "created_at"),
        Index("ix_call_org_rep", "org_id", "rep_name"),
        Index("ix_call_processing_status", "processing_status"),
    )


class Transcript(Base):
    __tablename__ = "transcript"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    call_id = Column(GUID(), ForeignKey("call.id"), unique=True, nullable=False)
    full_text = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    asr_provider = Column(String(50), nullable=False)
    asr_model = Column(String(100), nullable=True)
    asr_confidence = Column(Float, default=0.0)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("Call", back_populates="transcript")
    segments = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        order_by="TranscriptSegment.segment_index",
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segment"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    transcript_id = Column(GUID(), ForeignKey("transcript.id"), nullable=False)
    segment_index = Column(Integer, nullable=False)
    speaker_name = Column(String(100), nullable=False)
    speaker_role = Column(String(20), default="unknown")  # rep|buyer|unknown
    start_time_ms = Column(Integer, nullable=False)
    end_time_ms = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)

    transcript = relationship("Transcript", back_populates="segments")

    __table_args__ = (
        Index("ix_transcript_segment_transcript_time", "transcript_id", "start_time_ms"),
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_run"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    call_id = Column(GUID(), ForeignKey("call.id"), nullable=False)
    run_number = Column(Integer, nullable=False)  # 1, 2, 3...
    settings_snapshot = Column(JSONB, default=dict)  # exact config used
    summary = Column(JSONB, default=dict)  # rich summary from summary_node
    status = Column(String(20), default="processing")  # processing|complete|failed|partial
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    call = relationship("Call", back_populates="analysis_runs")
    pass1_result = relationship("Pass1Result", back_populates="analysis_run", uselist=False)
    framework_results = relationship("FrameworkResult", back_populates="analysis_run")
    insights = relationship("Insight", back_populates="analysis_run")

    __table_args__ = (
        UniqueConstraint("call_id", "run_number", name="uq_analysis_run_call_run"),
    )


class Pass1Result(Base):
    __tablename__ = "pass1_result"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    analysis_run_id = Column(GUID(), ForeignKey("analysis_run.id"), unique=True, nullable=False)
    hedge_data = Column(JSONB, default=list)
    sentiment_data = Column(JSONB, default=list)
    appraisal_data = Column(JSONB, default=list)
    prompt_version = Column(String(20), default="v1")
    model_used = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis_run = relationship("AnalysisRun", back_populates="pass1_result")


class FrameworkResult(Base):
    __tablename__ = "framework_result"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    analysis_run_id = Column(GUID(), ForeignKey("analysis_run.id"), nullable=False)
    framework_id = Column(String(20), nullable=False)  # e.g. "FW-01"
    framework_version = Column(String(20), nullable=False)
    prompt_version = Column(String(20), nullable=False)
    model_used = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    prompt_group = Column(String(5), nullable=False)  # A|B|C|D|E
    score = Column(Float, nullable=True)  # 0-100
    severity = Column(String(10), nullable=False)  # red|orange|yellow|green
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    headline = Column(String(80), nullable=False)
    explanation = Column(Text, nullable=False)
    evidence = Column(JSONB, default=list)  # array of segment refs
    coaching_recommendation = Column(Text, nullable=False)
    raw_output = Column(JSONB, default=dict)  # full LLM response
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis_run = relationship("AnalysisRun", back_populates="framework_results")
    sourced_insights = relationship("Insight", back_populates="framework_result")

    __table_args__ = (
        Index("ix_framework_result_run", "analysis_run_id"),
        Index("ix_framework_result_framework_severity", "framework_id", "severity"),
    )


class Insight(Base):
    __tablename__ = "insight"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    call_id = Column(GUID(), ForeignKey("call.id"), nullable=False)
    analysis_run_id = Column(GUID(), ForeignKey("analysis_run.id"), nullable=False)
    framework_result_id = Column(GUID(), ForeignKey("framework_result.id"), nullable=False)
    priority_rank = Column(Integer, default=0)
    is_top_insight = Column(Boolean, default=False)
    is_aim_null_finding = Column(Boolean, default=False)  # AIM null finding flag
    # Denormalized content from FrameworkResult for easier querying
    framework_name = Column(String(80), nullable=False)
    severity = Column(String(10), nullable=False)  # red|orange|yellow|green
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    headline = Column(String(80), nullable=False)
    explanation = Column(Text, nullable=False)
    evidence = Column(JSONB, default=list)  # array of segment refs
    coaching_recommendation = Column(Text, nullable=False)
    feedback = Column(String(20), nullable=True)  # positive|negative|null
    feedback_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("Call", back_populates="insights")
    analysis_run = relationship("AnalysisRun", back_populates="insights")
    framework_result = relationship("FrameworkResult", back_populates="sourced_insights")

    __table_args__ = (
        Index("ix_insight_call_run_rank", "call_id", "analysis_run_id", "priority_rank"),
    )


class BaseMetric(Base):
    __tablename__ = "base_metric"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    call_id = Column(GUID(), ForeignKey("call.id"), nullable=False)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(JSONB, default=dict)  # flexible shape per metric
    computed_from = Column(String(20), default="transcript")  # audio|transcript
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("Call", back_populates="base_metrics")

    __table_args__ = (
        UniqueConstraint("call_id", "metric_name", name="uq_base_metric_call_name"),
    )


class Setting(Base):
    __tablename__ = "setting"

    id = Column(GUID(), primary_key=True, default=uuid_lib.uuid4)
    user_id = Column(GUID(), ForeignKey("user.id"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(JSONB, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")

    __table_args__ = (
        UniqueConstraint("user_id", "setting_key", name="uq_setting_user_key"),
    )

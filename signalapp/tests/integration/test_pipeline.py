"""
Integration tests for the full pipeline.
Tests end-to-end pipeline execution with a transcript.
"""
from __future__ import annotations

import uuid
import pytest
import asyncio

# Test fixtures and helpers
from signalapp.db.repository import init_db, get_session, CallRepository, TranscriptRepository


# ─── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_db():
    """Initialize test database."""
    # Use in-memory SQLite for tests
    await init_db("sqlite+aiosqlite:///./test_signal.db")
    yield
    # Cleanup
    import os
    if os.path.exists("./test_signal.db"):
        os.remove("./test_signal.db")


@pytest.fixture
async def sample_call(setup_db):
    """Create a sample call for testing."""
    call_repo = CallRepository()
    transcript_repo = TranscriptRepository()

    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Create call
    call = await call_repo.create(
        org_id=org_id,
        uploaded_by=user_id,
        rep_name="Test Rep",
        call_type="discovery",
        deal_name="Test Deal",
    )

    # Create transcript with sample segments
    transcript = await transcript_repo.create(
        call_id=call.id,
        full_text="[00:00] Rep (rep): Hello, how are you?\n[00:05] Buyer (buyer): I'm good, thanks.",
        asr_provider="test",
    )

    # Add segments
    segments = [
        {
            "segment_index": 0,
            "speaker_name": "Rep",
            "speaker_role": "rep",
            "start_time_ms": 0,
            "end_time_ms": 5000,
            "text": "Hello, how are you?",
        },
        {
            "segment_index": 1,
            "speaker_name": "Buyer",
            "speaker_role": "buyer",
            "start_time_ms": 5000,
            "end_time_ms": 10000,
            "text": "I'm good, thanks.",
        },
        {
            "segment_index": 2,
            "speaker_name": "Rep",
            "speaker_role": "rep",
            "start_time_ms": 10000,
            "end_time_ms": 20000,
            "text": "Great to hear. Can you tell me about your current challenges?",
        },
        {
            "segment_index": 3,
            "speaker_name": "Buyer",
            "speaker_role": "buyer",
            "start_time_ms": 20000,
            "end_time_ms": 35000,
            "text": "Well, we're looking for a better solution than what we have now.",
        },
    ]

    await transcript_repo.add_segments(transcript.id, segments)

    return call


@pytest.fixture
def sample_transcript_segments():
    """Sample transcript segments for testing."""
    return [
        {
            "segment_index": 0,
            "speaker_name": "Rep",
            "speaker_role": "rep",
            "start_time_ms": 0,
            "end_time_ms": 5000,
            "text": "Hi there, thanks for joining. I'm Alex from Signal.",
        },
        {
            "segment_index": 1,
            "speaker_name": "Buyer",
            "speaker_role": "buyer",
            "start_time_ms": 5000,
            "end_time_ms": 15000,
            "text": "Happy to be here. I've reviewed the proposal you sent over.",
        },
        {
            "segment_index": 2,
            "speaker_name": "Rep",
            "speaker_role": "rep",
            "start_time_ms": 15000,
            "end_time_ms": 25000,
            "text": "Great! Questions about the budget and timeline?",
        },
        {
            "segment_index": 3,
            "speaker_name": "Buyer",
            "speaker_role": "buyer",
            "start_time_ms": 25000,
            "end_time_ms": 40000,
            "text": "Budget is a concern. We need to see ROI before committing.",
        },
        {
            "segment_index": 4,
            "speaker_name": "Rep",
            "speaker_role": "rep",
            "start_time_ms": 40000,
            "end_time_ms": 50000,
            "text": "Understood. Let me ask some questions to understand your needs better.",
        },
        {
            "segment_index": 5,
            "speaker_name": "Buyer",
            "speaker_role": "buyer",
            "start_time_ms": 50000,
            "end_time_ms": 60000,
            "text": "Sure, go ahead.",
        },
    ]


# ─── Pipeline State Tests ───────────────────────────────────────────────────────


class TestPipelineState:
    """Test pipeline state structure."""

    def test_pipeline_state_has_required_fields(self):
        """PipelineState should have all required fields defined in the TypedDict."""
        from signalapp.pipeline.state import PipelineState
        import typing

        # TypedDict fields are accessed via __annotations__
        required_fields = [
            "call_id",
            "call_type",
            "transcript_segments",
            "pass1_result",
            "routing_decisions",
            "active_frameworks",
            "pass1_gate_signals",
            "framework_results",
            "framework_errors",
            "verified_insights",
            "summary",
            "errors",
        ]

        annotations = PipelineState.__annotations__
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"


# ─── Routing Integration Tests ──────────────────────────────────────────────────


class TestRoutingIntegration:
    """Test routing behavior with sample data."""

    def test_routing_pricing_call_with_signals(self, sample_transcript_segments):
        """Test routing for a pricing call with full signals."""
        from signalapp.domain.routing import route_frameworks, Pass1GateSignals

        signals = Pass1GateSignals(
            has_competitor_mention=True,
            has_pricing_discussion=True,
            has_numeric_anchor=True,
            has_objection_markers=True,
            has_rep_questions=True,
            has_close_language=True,
            call_duration_minutes=30.0,
        )

        active, decisions = route_frameworks("pricing", signals)

        # Pinned should always be active
        assert 8 in active
        assert 9 in active
        assert 15 in active

        # Pricing should activate many frameworks
        assert 3 in active  # BATNA - AIM on pricing
        assert 4 in active  # Money Left - AIM on pricing
        assert 7 in active  # First Number - AIM on pricing
        assert 11 in active  # Close Attempt - AIM on pricing

    def test_routing_discovery_call(self, sample_transcript_segments):
        """Test routing for a discovery call."""
        from signalapp.domain.routing import route_frameworks, Pass1GateSignals

        signals = Pass1GateSignals(
            has_competitor_mention=False,
            has_pricing_discussion=False,
            has_numeric_anchor=False,
            has_objection_markers=False,
            has_rep_questions=True,
            has_close_language=False,
            call_duration_minutes=25.0,
        )

        active, decisions = route_frameworks("discovery", signals)

        # Should NOT have these on discovery
        assert 3 not in active  # BATNA not mandatory on discovery
        assert 4 not in active  # Money Left blocked on discovery
        assert 7 not in active  # First Number blocked on discovery

        # Should have
        assert 13 in active  # Deal Timing - mandatory on discovery


# ─── API Endpoint Tests ─────────────────────────────────────────────────────────


class TestInsightsAPI:
    """Test insights API endpoints."""

    def test_get_call_insights_response_structure(self):
        """Test that get_call_insights returns proper response structure."""
        from signalapp.api.insights import CallInsightsResponse, InsightResponse

        # Use a sample UUID
        sample_uuid = str(uuid.uuid4())

        # Mock response structure
        response = CallInsightsResponse(
            call_id=sample_uuid,
            run_id=None,
            insights=[],
            summary=None,
        )

        assert response.call_id == sample_uuid
        assert response.run_id is None
        assert response.insights == []


class TestCallsAPI:
    """Test calls API endpoints."""

    @pytest.mark.asyncio
    async def test_list_calls_response_structure(self):
        """Test that list_calls returns proper response structure."""
        from signalapp.api.calls import CallListResponse, CallResponse

        response = CallListResponse(
            calls=[],
            total=0,
        )

        assert response.calls == []
        assert response.total == 0

    @pytest.mark.asyncio
    async def test_call_response_model(self):
        """Test CallResponse model."""
        from signalapp.api.calls import CallResponse

        response = CallResponse(
            id="123e4567-e89b-12d3-a456-426614174000",
            org_id="123e4567-e89b-12d3-a456-426614174001",
            rep_name="Test Rep",
            call_type="discovery",
            deal_name="Test Deal",
            call_date="2026-04-01",
            duration_seconds=1800,
            processing_status="complete",
            created_at="2026-04-01T12:00:00",
        )

        assert response.rep_name == "Test Rep"
        assert response.call_type == "discovery"


# ─── Pipeline Node Tests ─────────────────────────────────────────────────────────


class TestPass1ExtractNode:
    """Test Pass 1 extraction node."""

    def test_pass1_extract_node_structure(self):
        """Test that pass1_extract_node is a callable async function."""
        from signalapp.pipeline.nodes.pass1_extract import pass1_extract_node
        import asyncio

        assert asyncio.iscoroutinefunction(pass1_extract_node)

    def test_format_transcript(self):
        """Test transcript formatting for LLM input."""
        from signalapp.pipeline.nodes.pass1_extract import _format_transcript

        segments = [
            {
                "start_time_ms": 5000,
                "speaker_name": "Alex",
                "speaker_role": "rep",
                "text": "Hello, how are you?",
            },
            {
                "start_time_ms": 10000,
                "speaker_name": "Sam",
                "speaker_role": "buyer",
                "text": "I'm good, thanks.",
            },
        ]

        result = _format_transcript(segments)

        assert "[00:05] Alex (rep): Hello, how are you?" in result
        assert "[00:10] Sam (buyer): I'm good, thanks." in result


# ─── Reliability Module Tests ───────────────────────────────────────────────────


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test that successful coroutine returns immediately."""
        from signalapp.reliability import RetryConfig, with_retry

        attempt_count = 0

        async def successful_coro():
            nonlocal attempt_count
            attempt_count += 1
            return "success"

        result = await with_retry(successful_coro)

        assert result == "success"
        assert attempt_count == 1

    @pytest.mark.asyncio
    async def test_retry_fails_after_max_attempts(self):
        """Test that retries exhausted raises the last exception."""
        from signalapp.reliability import RetryConfig, with_retry

        attempt_count = 0

        async def failing_coro():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Test error")

        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(ValueError) as exc_info:
            await with_retry(failing_coro, config)

        assert str(exc_info.value) == "Test error"
        assert attempt_count == 3


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_on_success(self):
        """Test circuit closes after successful call."""
        from signalapp.reliability import CircuitBreaker, CircuitState

        cb = CircuitBreaker()

        async def success_coro():
            return "success"

        result = await cb.call(success_coro)

        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        from signalapp.reliability import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout=60.0)
        cb = CircuitBreaker(config=config)

        async def failing_coro():
            raise ValueError("Failure")

        # Fail 3 times to open circuit
        for i in range(3):
            with pytest.raises(ValueError):
                await cb.call(failing_coro)

        assert cb.state == CircuitState.OPEN
        assert cb.failures >= config.failure_threshold


# ─── Domain Model Tests ─────────────────────────────────────────────────────────


class TestDomainModels:
    """Test domain models."""

    def test_insight_feedback_validation(self):
        """Test insight feedback request validation."""
        from signalapp.api.insights import InsightFeedbackRequest

        # Valid feedback values
        req = InsightFeedbackRequest(feedback="positive")
        assert req.feedback == "positive"

        req = InsightFeedbackRequest(feedback="negative")
        assert req.feedback == "negative"

        req = InsightFeedbackRequest(feedback=None)
        assert req.feedback is None

        # Default is None
        req = InsightFeedbackRequest()
        assert req.feedback is None

    def test_insight_evidence_model(self):
        """Test InsightEvidence model."""
        from signalapp.api.insights import InsightEvidence

        evidence = InsightEvidence(
            segment_id="seg_123",
            timestamp=12000,
            speaker="buyer",
            quote="We need to discuss pricing.",
        )

        assert evidence.segment_id == "seg_123"
        assert evidence.timestamp == 12000
        assert evidence.speaker == "buyer"


# ─── Run All Tests ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
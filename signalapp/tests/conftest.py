"""Shared pytest fixtures for signalapp tests."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock
from datetime import datetime
import uuid


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_call_id() -> uuid.UUID:
    """Return a valid UUID for testing."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def sample_transcript_segments() -> list[dict]:
    """Return sample transcript segments for testing."""
    return [
        {
            "segment_index": 0,
            "speaker_name": "Alex",
            "speaker_role": "rep",
            "start_time_ms": 0,
            "end_time_ms": 30000,
            "text": "Hi Sarah, thanks for joining today. I wanted to walk you through our pricing.",
        },
        {
            "segment_index": 1,
            "speaker_name": "Sarah",
            "speaker_role": "buyer",
            "start_time_ms": 30000,
            "end_time_ms": 60000,
            "text": "Thanks for having me. I'm curious about your pricing model.",
        },
        {
            "segment_index": 2,
            "speaker_name": "Alex",
            "speaker_role": "rep",
            "start_time_ms": 60000,
            "end_time_ms": 90000,
            "text": "Sure. We have three tiers: Starter at $500/mo, Professional at $1000/mo, and Enterprise at $2500/mo.",
        },
        {
            "segment_index": 3,
            "speaker_name": "Sarah",
            "speaker_role": "buyer",
            "start_time_ms": 90000,
            "end_time_ms": 120000,
            "text": "Those prices seem high. What about if we pay annually?",
        },
        {
            "segment_index": 4,
            "speaker_name": "Alex",
            "speaker_role": "rep",
            "start_time_ms": 120000,
            "end_time_ms": 150000,
            "text": "We do offer a 20% discount for annual billing. That brings Professional to $9600/year.",
        },
        {
            "segment_index": 5,
            "speaker_name": "Sarah",
            "speaker_role": "buyer",
            "start_time_ms": 150000,
            "end_time_ms": 180000,
            "text": "That's better. Can you send me a proposal?",
        },
    ]


@pytest.fixture
def sample_pipeline_state(sample_transcript_segments) -> dict:
    """Return a sample pipeline state dict."""
    return {
        "call_id": "11111111-1111-1111-1111-111111111111",
        "call_type": "pricing",
        "transcript_segments": sample_transcript_segments,
        "active_frameworks": {1, 2, 3, 5, 6, 8, 9, 15},
        "pass1_result": {
            "hedge_data": [
                {
                    "segment_id": "seg_abc123",
                    "hedge_text": "seems high",
                    "hedge_type": "epistemic",
                    "confidence": 0.85,
                }
            ],
            "sentiment_data": [
                {"segment_id": "seg_abc123", "sentiment_score": -0.2, "confidence": 0.7, "notable_shift": False}
            ],
            "appraisal_data": [],
            "contains_comparison_language": False,
            "contains_dollar_amount": True,
            "first_number_speaker": "rep",
            "transcript_duration_minutes": 3.0,
            "hedge_density_buyer": 0.05,
            "hedge_density_rep": 0.02,
            "prompt_version": "v1",
            "model_used": "gemini",
            "model_version": "gemini-2.5-flash",
        },
        "errors": [],
    }


@pytest.fixture
def mock_llm_provider():
    """Return a mock LLM provider that returns stub responses."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.complete_structured = AsyncMock(return_value=MagicMock(
        model_validate_json=MagicMock(return_value=MagicMock(
            model_dump=MagicMock(return_value={})
        ))
    ))
    return mock

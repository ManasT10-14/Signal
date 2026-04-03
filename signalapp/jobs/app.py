"""
ARQ application configuration — supports both Redis and in-memory modes.

Use QUEUE_MODE env var:
  - "memory" → use in-memory queue (no Redis needed, for dev only)
  - "redis"  → use ARQ + Redis (production)
"""
from __future__ import annotations

from signalapp.app.config import get_config


def get_arq_settings() -> dict:
    """
    ARQ worker settings.
    Only used when QUEUE_MODE=redis.
    """
    config = get_config()
    return {
        "name": "signal-worker",
        "database_url": config.redis_url,
        "max_jobs": 10,
        "job_timeout": 600,  # 10 minutes max per job
        "keep_result": 3600,  # Keep results for 1 hour
        "retry_delay": 60,
        "max_retries": 3,
    }


def get_queue_mode() -> str:
    """Return the queue mode: 'memory' or 'redis'."""
    return get_config().queue_mode


# Queue names
QUEUE_TRANSCRIPTION = "transcription"
QUEUE_PREPROCESSING = "preprocessing"
QUEUE_PIPELINE = "pipeline"

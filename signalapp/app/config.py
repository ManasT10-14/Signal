"""
Application configuration — loaded from environment variables and .env file.
All config is accessed through this module. No hardcoded values.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — rely on real env vars


@dataclass
class LLMGroupConfig:
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.1
    max_tokens: int = 8192   # Safe upper limit for Gemini structured output
    fallback_model: Optional[str] = None


@dataclass
class AppConfig:
    # Environment
    environment: str = "development"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])

    # ── Database ──────────────────────────────────────────────────────────────
    # Use SQLITE_URL (for local dev) or DATABASE_URL (Postgres)
    database_url: str = ""
    sqlite_url: str = "sqlite+aiosqlite:///./signal_dev.db"

    @property
    def db_url(self) -> str:
        """Return the active database URL. Only use database_url if it looks valid."""
        if self.database_url and "://" in self.database_url:
            return self.database_url
        return self.sqlite_url

    # ── Queue ────────────────────────────────────────────────────────────────
    # QUEUE_MODE=memory (dev) or QUEUE_MODE=redis (production)
    queue_mode: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"

    # ── GCP / Vertex AI ─────────────────────────────────────────────────────
    gcp_project: str = ""
    gcp_location: str = "us-central1"
    vertex_enabled: bool = True

    # ── Gemini (legacy direct API — used when vertex_enabled=false) ──────────
    gemini_api_key: str = ""

    # LLM Configuration (per prompt group — temperatures from LLM_RELIABILITY_GUIDE)
    llm_pass1: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.0))      # Extraction
    llm_group_a: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.05))    # Classification
    llm_group_b: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.05))    # Classification
    llm_group_c: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.10))    # Interpretation
    llm_group_d: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.10))    # NEPQ methodology
    llm_group_e: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.10))    # Interpretation
    llm_summary: LLMGroupConfig = field(default_factory=lambda: LLMGroupConfig(temperature=0.25))    # Generation

    # Langfuse
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Pipeline
    max_concurrent_calls: int = 3
    llm_timeout_seconds: int = 120
    debug_mode: bool = False


def load_config() -> AppConfig:
    """Load configuration from environment variables and .env file."""
    config = AppConfig()

    config.environment = os.getenv("SIGNAL_ENV", "development")
    config.debug_mode = os.getenv("SIGNAL_DEBUG", "false").lower() == "true"

    # Database
    config.database_url = os.getenv("DATABASE_URL", "")
    config.sqlite_url = os.getenv("SQLITE_URL", "sqlite+aiosqlite:///./signal_dev.db")

    # Queue
    config.queue_mode = os.getenv("QUEUE_MODE", "memory")
    config.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # GCP / Vertex AI
    config.gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    config.gcp_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    config.vertex_enabled = os.getenv("VERTEX_ENABLED", "true").lower() == "true"
    config.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

    # AWS (removed — S3 disabled in transcript-only mode)
    # API Keys (ASR keys removed in transcript-only mode)

    # Langfuse
    if lf_public := os.getenv("LANGFUSE_PUBLIC_KEY"):
        config.langfuse_public_key = lf_public
    if lf_secret := os.getenv("LANGFUSE_SECRET_KEY"):
        config.langfuse_secret_key = lf_secret

    # LLM model overrides
    if model := os.getenv("SIGNAL_LLM_MODEL"):
        for group_config in [
            config.llm_pass1,
            config.llm_group_a,
            config.llm_group_b,
            config.llm_group_c,
            config.llm_group_d,
            config.llm_group_e,
            config.llm_summary,
        ]:
            group_config.model = model

    return config


# Global config instance — import this in all modules
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config

"""
Gemini LLM adapter — supports Vertex AI and direct Gemini API.

Vertex AI (recommended):
  GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION + VERTEX_ENABLED=true
  Auth via: gcloud auth application-default login

Direct API (legacy):
  GEMINI_API_KEY + VERTEX_ENABLED=false
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

from google.genai import types
import google.genai as genai
from pydantic import ValidationError

from .base import LLMProvider, LLMResponse, LLMConfig, LLMValidationError

logger = logging.getLogger(__name__)

GEMINI_INPUT_COST_PER_M = 0.075
GEMINI_OUTPUT_COST_PER_M = 0.30

# Default timeout for LLM calls (seconds)
LLM_TIMEOUT_SECONDS = 120


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        *,
        vertex_enabled: bool | None = None,
        gcp_project: str | None = None,
        gcp_location: str | None = None,
    ):
        self._client = None
        self._mode: str | None = None

        if vertex_enabled is None:
            vertex_enabled = os.getenv("VERTEX_ENABLED", "true").lower() == "true"

        if vertex_enabled:
            self._mode = "vertex"
            self._gcp_project = gcp_project or os.getenv("GOOGLE_CLOUD_PROJECT", "")
            self._gcp_location = gcp_location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            self._api_key = None
        else:
            self._mode = "direct"
            self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
            self._gcp_project = ""
            self._gcp_location = "us-central1"

    def _get_client(self):
        if self._client is None:
            if self._mode == "vertex":
                if not self._gcp_project:
                    raise ValueError("GOOGLE_CLOUD_PROJECT not set.")
                self._client = genai.Client(
                    vertexai=True,
                    project=self._gcp_project,
                    location=self._gcp_location,
                )
            elif self._mode == "direct":
                if not self._api_key:
                    raise ValueError("GEMINI_API_KEY not set.")
                self._client = genai.Client(api_key=self._api_key)
            else:
                raise ValueError("Unknown mode")
        return self._client

    async def complete_structured(
        self,
        prompt: str,
        response_model: type,
        config: LLMConfig,
    ):
        start = time.perf_counter()
        client = self._get_client()

        # Build GenerateContentConfig as a Pydantic model (SDK 1.62.0+)
        gen_config = types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
            response_mime_type="application/json",
            response_schema=response_model,
        )

        # Run blocking SDK call in thread pool with timeout
        loop = asyncio.get_event_loop()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=config.model,
                        contents=prompt,
                        config=gen_config,
                    ),
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise LLMValidationError(
                f"Gemini API call timed out after {LLM_TIMEOUT_SECONDS}s",
                raw_text="",
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        raw_text = response.text or ""
        tokens_input = len(prompt) // 4
        tokens_output = len(raw_text) // 4
        cost_usd = (
            tokens_input / 1_000_000 * GEMINI_INPUT_COST_PER_M
            + tokens_output / 1_000_000 * GEMINI_OUTPUT_COST_PER_M
        )

        # Parse and validate response
        try:
            parsed = response_model.model_validate_json(raw_text)
        except (ValidationError, json.JSONDecodeError) as e:
            raise LLMValidationError(
                f"Response failed schema validation: {e}",
                raw_text=raw_text,
            ) from e

        return parsed

    async def complete(self, prompt: str, config: LLMConfig) -> LLMResponse:
        start = time.perf_counter()
        client = self._get_client()

        gen_config = types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )

        # Run blocking SDK call in thread pool with timeout
        loop = asyncio.get_event_loop()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=config.model,
                        contents=prompt,
                        config=gen_config,
                    ),
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise LLMValidationError(
                f"Gemini API call timed out after {LLM_TIMEOUT_SECONDS}s",
                raw_text="",
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        raw_text = response.text or ""
        tokens_input = len(prompt) // 4
        tokens_output = len(raw_text) // 4
        cost_usd = (
            tokens_input / 1_000_000 * GEMINI_INPUT_COST_PER_M
            + tokens_output / 1_000_000 * GEMINI_OUTPUT_COST_PER_M
        )

        return LLMResponse(
            content=raw_text,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            model=config.model,
        )

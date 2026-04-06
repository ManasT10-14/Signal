"""
LLM Provider interface — all LLM adapters implement this contract.
Provider-agnostic: swap Gemini for Anthropic/OpenAI by implementing this interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    cost_usd: float
    model: str


@dataclass
class LLMConfig:
    model: str
    temperature: float
    max_tokens: int
    provider: str  # "gemini" | "anthropic" | "openai"


class LLMValidationError(Exception):
    """Raised when LLM response fails schema validation."""

    def __init__(self, message: str, raw_text: str = ""):
        super().__init__(message)
        self.raw_text = raw_text


class LLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    All providers must implement structured output via JSON schema validation.
    """

    @abstractmethod
    async def complete_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        config: LLMConfig,
    ) -> BaseModel:
        """
        Generate a response conforming to the Pydantic response_model.
        Uses native JSON schema validation (no Instructor needed).
        """
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        config: LLMConfig,
    ) -> LLMResponse:
        """
        Generate a plain text response.
        """
        ...

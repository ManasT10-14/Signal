"""
Retry logic with exponential backoff for LLM calls.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    exponential_base: float = 2.0
    max_delay: float = 30.0
    jitter: bool = True  # Add randomness to prevent thundering herd

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (1-based)."""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay *= (0.5 + random.random())  # 50-100% of delay
        return delay


async def with_retry(
    coro: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
) -> T:
    """
    Execute a coroutine with retry logic.

    Args:
        coro: Async callable to execute
        config: Retry configuration. Defaults to RetryConfig()

    Returns:
        The result of the coroutine

    Raises:
        The last exception if all retries are exhausted
    """
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await coro()
        except Exception as e:
            last_exception = e
            if attempt == config.max_attempts:
                break

            delay = config.get_delay(attempt)
            await asyncio.sleep(delay)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Retry exhausted with no exception recorded")
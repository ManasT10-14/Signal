"""
Circuit breaker pattern for LLM calls.
Prevents cascading failures when a service is degraded.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"           # Failure threshold exceeded, requests rejected
    HALF_OPEN = "half-open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5       # Number of failures before opening
    reset_timeout: float = 60.0     # Seconds before trying half-open
    half_open_max_calls: int = 1    # Max test calls in half-open state


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for protecting LLM calls from cascading failures.

    State transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After reset_timeout seconds
    - HALF_OPEN -> CLOSED: If test call succeeds
    - HALF_OPEN -> OPEN: If test call fails
    """
    failures: int = 0
    successes: int = 0
    last_failure_time: float = field(default=0.0)
    state: CircuitState = CircuitState.CLOSED
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    async def call(self, coro: Callable[[], Awaitable[T]]) -> T:
        """
        Execute a coroutine through the circuit breaker.

        Args:
            coro: Async callable to execute

        Returns:
            The result of the coroutine

        Raises:
            CircuitBreakerOpen: If the circuit is open
        """
        now = time.time()

        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.config.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
            else:
                raise CircuitBreakerOpen(
                    f"Circuit is OPEN. Retry after {self.config.reset_timeout - (now - self.last_failure_time):.1f}s"
                )

        # Execute the call
        try:
            result = await coro()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= self.config.half_open_max_calls:
                # Recovery successful - close the circuit
                self.state = CircuitState.CLOSED
                self.failures = 0
        else:
            # Reset failure count in closed state
            self.failures = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.last_failure_time = time.time()
        self.failures += 1

        if self.state == CircuitState.HALF_OPEN:
            # Failed during test - go back to open
            self.state = CircuitState.OPEN
        elif self.failures >= self.config.failure_threshold:
            # Too many failures in closed state - open the circuit
            self.state = CircuitState.OPEN

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    pass
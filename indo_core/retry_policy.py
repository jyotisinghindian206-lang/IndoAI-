"""Bounded retry/backoff primitives for network providers.

Callers decide which provider errors are retryable; this module never retries blindly.
"""
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Callable, TypeVar
T = TypeVar("T")

@dataclass(frozen=True)
class RetryPlan:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0
    jitter_ratio: float = 0.15

    def __post_init__(self):
        if self.max_attempts < 1 or self.max_attempts > 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("Retry delays must be non-negative and max must be >= base")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")

    def delay_for(self, failed_attempt: int, random_source: Callable[[], float] = random.random) -> float:
        if failed_attempt < 1:
            raise ValueError("failed_attempt starts at 1")
        base = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (failed_attempt - 1)))
        spread = base * self.jitter_ratio
        return max(0.0, min(self.max_delay_seconds, base + (2 * random_source() - 1) * spread))


def call_with_retry(operation: Callable[[], T], retryable: Callable[[Exception], bool],
                    plan: RetryPlan = RetryPlan(), sleep: Callable[[float], None] | None = None,
                    random_source: Callable[[], float] = random.random) -> T:
    """Run operation with bounded retries and caller-supplied error classification."""
    import time
    wait = sleep or time.sleep
    for attempt in range(1, plan.max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= plan.max_attempts or not retryable(exc):
                raise
            delay = plan.delay_for(attempt, random_source)
            if delay:
                wait(delay)
    raise RuntimeError("Unreachable retry state")

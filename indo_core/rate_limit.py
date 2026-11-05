"""In-memory sliding-window limiter for single-process development deployments."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Callable

@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: float
    limit: int
    window_seconds: float

class SlidingWindowLimiter:
    """Thread-safe limiter. Use Redis/shared storage for multi-worker production."""
    def __init__(self, limit: int = 60, window_seconds: float = 60,
                 clock: Callable[[], float] = time.monotonic, max_keys: int = 20_000):
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit must be positive and window_seconds must be > 0")
        self.limit = int(limit)
        self.window = float(window_seconds)
        self.clock = clock
        self.max_keys = max(100, int(max_keys))
        self._events: dict[str, deque[float]] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = threading.RLock()

    def _trim(self, key: str, now: float) -> deque[float]:
        events = self._events.setdefault(key, deque())
        cutoff = now - self.window
        while events and events[0] <= cutoff:
            events.popleft()
        self._last_seen[key] = now
        return events

    def _evict_if_needed(self) -> None:
        if len(self._events) <= self.max_keys:
            return
        excess = len(self._events) - self.max_keys
        oldest = sorted(self._last_seen, key=self._last_seen.get)[:excess]
        for key in oldest:
            self._events.pop(key, None)
            self._last_seen.pop(key, None)

    def check(self, key: object, consume: bool = True) -> LimitDecision:
        normalized_key = str(key).strip()[:256] or "anonymous"
        now = self.clock()
        with self._lock:
            events = self._trim(normalized_key, now)
            allowed = len(events) < self.limit
            retry = 0.0 if allowed or not events else max(0.0, events[0] + self.window - now)
            if allowed and consume:
                events.append(now)
            self._evict_if_needed()
            return LimitDecision(allowed, max(0, self.limit - len(events)), retry,
                                 self.limit, self.window)

    def reset(self, key: object | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
                self._last_seen.clear()
            else:
                normalized = str(key).strip()[:256] or "anonymous"
                self._events.pop(normalized, None)
                self._last_seen.pop(normalized, None)

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            return {"tracked_keys": len(self._events), "limit": self.limit,
                    "window_seconds": self.window, "max_keys": self.max_keys}

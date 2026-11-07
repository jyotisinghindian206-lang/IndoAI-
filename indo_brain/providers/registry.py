"""Provider capability metadata; never treats key presence as proof of health."""
from __future__ import annotations
from typing import Any

class ProviderRegistry:
    def __init__(self): self._items: dict[str, dict[str, Any]] = {}
    def register(self, name: str, *, capabilities=(), enabled=False, health="unknown", latency_ms=None, cost_per_1k=None):
        key = str(name).strip().lower()
        if not key: raise ValueError("provider name is required")
        self._items[key] = {"name": key, "capabilities": sorted({str(x).lower() for x in capabilities}),
                            "enabled": bool(enabled), "health": str(health),
                            "latency_ms": latency_ms, "cost_per_1k": cost_per_1k}
    def snapshot(self): return [dict(v) for v in self._items.values()]
    def candidates(self):
        return [{**v, "available": v["enabled"] and v["health"] == "healthy"}
                for v in self._items.values()]

from __future__ import annotations
from typing import Any
from ..vishnu_core import select_provider

def route_provider(candidates: list[dict[str, Any]], required_capabilities: list[str] | None = None):
    """Select only from explicit healthy status snapshots supplied by the caller."""
    normalized = []
    for item in candidates[:30]:
        if not isinstance(item, dict): continue
        normalized.append({**item, "available": bool(item.get("available")) and item.get("health") == "healthy"})
    return select_provider(normalized, required_capabilities or [])

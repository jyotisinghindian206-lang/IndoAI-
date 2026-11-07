from __future__ import annotations
from typing import Any
from ..intelligence import plan_intelligence
from .orchestrator import build_agent_plan

def create_reasoning_plan(message: str, mode: str = "New Chat", attachment_count: int = 0,
                          history_count: int = 0, attachment_types: list[str] | None = None) -> dict[str, Any]:
    base = plan_intelligence(str(message)[:12000], str(mode)[:80], min(10, max(0, int(attachment_count))), min(500, max(0, int(history_count))))
    agents = build_agent_plan(base, attachment_types=attachment_types)
    return {**base, "architecture": "VISHNU hybrid reasoning", "agents": agents,
            "reasoning_controls": ["assumption_check", "approach_comparison", "independent_verification", "uncertainty_reporting"],
            "chain_of_thought_disclosure": "not_provided; concise rationale only", "provider_calls_made": 0}

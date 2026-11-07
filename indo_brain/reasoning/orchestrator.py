"""Hybrid deterministic agent orchestration used to guide configured model calls."""
from __future__ import annotations
from typing import Any
from ..agents import (ReasoningAgent, ResearchAgent, CodingAgent,
                      VerificationAgent, MemoryAgent, MultimodalAgent)

_AGENTS = {
    "reasoning": ReasoningAgent(), "research": ResearchAgent(),
    "coding": CodingAgent(), "verification": VerificationAgent(),
    "memory": MemoryAgent(), "multimodal": MultimodalAgent(),
}

def build_agent_plan(plan: dict[str, Any], *, attachment_types: list[str] | None = None) -> dict[str, Any]:
    intent = str(plan.get("intent", "general"))
    deep = str(plan.get("lane", "standard")) in {"deep", "intensive"}
    selected = ["reasoning", "verification"]
    if intent == "research": selected.insert(1, "research")
    if intent == "coding": selected.insert(1, "coding")
    if attachment_types: selected.append("multimodal")
    selected.append("memory")
    task = {"intent": intent, "deep": deep, "attachment_types": attachment_types or [],
            "memory_read_consent": False, "memory_write_consent": False}
    results = [_AGENTS[name].run(task).to_dict() for name in dict.fromkeys(selected)]
    return {"architecture": "hybrid_central_vishnu_specialists", "selected_agents": list(dict.fromkeys(selected)),
            "agent_results": results, "model_calls_made": 0,
            "execution_note": "These are local planning components. Actual provider/tool execution remains in existing Indo adapters and requires GARUDA authorization."}

def build_reasoning_directive(plan: dict[str, Any]) -> str:
    agent_plan = build_agent_plan(plan)
    agents = ", ".join(agent_plan["selected_agents"])
    return ("HYBRID VISHNU REASONING POLICY: Central VISHNU coordinates specialist roles (" + agents + "). "
            "Use concise task decomposition internally; do not reveal private chain-of-thought. "
            "Present conclusions, key assumptions, concise rationale, evidence and uncertainty. "
            "Do not claim a specialist ran a tool or model unless it actually did. "
            "For complex tasks, verify important outputs independently before final synthesis.")

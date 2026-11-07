"""Contracts for local specialist agents. Agents produce structured task notes, not hidden chain-of-thought."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class AgentResult:
    agent: str
    status: str
    summary: str
    outputs: dict[str, Any]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class BaseAgent:
    name = "base"
    def run(self, task: dict[str, Any]) -> AgentResult:
        return AgentResult(self.name, "not_implemented", "No specialist handler is configured.", {}, ["This agent does not call a model or external tool."])

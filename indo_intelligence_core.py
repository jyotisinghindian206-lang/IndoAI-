"""Unified control plane for Indo AI's six intelligence subsystems.

This module is intentionally lightweight: it reports component health and safe
capabilities without making network calls or delaying chat streaming.
"""
from __future__ import annotations
from typing import Any


class IndoIntelligenceCore:
    VERSION = "1.0.0"

    def __init__(self, *, anticipatory=None, persona_sync=None, project_threads=None,
                 devil_advocate=None, autonomous=None, hyperlocal=None, dlm=None):
        self.components = {
            "anticipatory_intelligence": anticipatory,
            "adaptive_persona_sync": persona_sync,
            "cross_session_project_threads": project_threads,
            "devils_advocate": devil_advocate,
            "autonomous_execution": autonomous,
            "hyper_local_intelligence": hyperlocal,
            "dynamic_learning_memory": dlm,
        }

    def status(self) -> dict[str, Any]:
        """Return non-sensitive health and capability information only."""
        features = {}
        for name, component in self.components.items():
            available = component is not None
            features[name] = {"available": available, "state": "ready" if available else "unavailable"}
        anticipatory = self.components.get("anticipatory_intelligence")
        research = anticipatory.status() if anticipatory is not None else {"enabled": False}
        ready = sum(1 for item in features.values() if item["available"])
        return {
            "core_version": self.VERSION,
            "state": "ready" if ready == len(features) else "degraded",
            "features_ready": ready,
            "features_total": len(features),
            "features": features,
            "background_research": {
                "enabled": bool(research.get("enabled", False)),
                "active_jobs": int(research.get("active_background_jobs", 0)),
                "cached_findings": int(research.get("cached_findings", 0)),
                "prepared_followups": int(research.get("prepared_followups", 0)),
            },
            "execution_policy": "approval-gated; no arbitrary code or external side effects",
            "location_policy": "coarse user-entered preferences only; no device geolocation",
            "streaming_policy": "background research is not awaited by the chat response path",
        }

from .base import BaseAgent, AgentResult
class MultimodalAgent(BaseAgent):
    name = "multimodal"
    def run(self, task):
        kinds = task.get("attachment_types", [])
        return AgentResult(self.name, "planned", "Use only modalities actually supplied and supported by the active provider.", {
            "provided_types": [str(x)[:30] for x in kinds[:20]] if isinstance(kinds, list) else [],
            "checks": ["identify visible or extracted content", "separate observation from inference", "report unreadable portions"]
        }, ["No attachment is opened or transmitted by this planner."])

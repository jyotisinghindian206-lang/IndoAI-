from .base import BaseAgent, AgentResult
class VerificationAgent(BaseAgent):
    name = "verification"
    def run(self, task):
        return AgentResult(self.name, "planned", "Select independent checks appropriate to the task.", {
            "checks": ["requirements coverage", "internal consistency", "calculation or test validation", "source traceability", "uncertainty disclosure"]
        }, ["A checklist cannot independently establish factual truth."])

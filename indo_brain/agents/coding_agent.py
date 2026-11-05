from .base import BaseAgent, AgentResult
class CodingAgent(BaseAgent):
    name = "coding"
    def run(self, task):
        return AgentResult(self.name, "planned", "Inspect before editing and validate every bounded change.", {
            "workflow": ["inspect actual files", "map dependencies", "preserve user data and secrets", "make minimal patch", "run targeted tests", "run regression tests"]
        }, ["No files are read or modified by this planner."])

from .base import BaseAgent, AgentResult
class ResearchAgent(BaseAgent):
    name = "research"
    def run(self, task):
        return AgentResult(self.name, "planned", "Research is needed only when freshness or external evidence matters.", {
            "source_requirements": ["prefer primary sources", "record publication dates", "compare independent sources", "cite retrieved sources"]
        }, ["No web request is made by this local planner."])

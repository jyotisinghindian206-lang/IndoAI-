from .base import BaseAgent, AgentResult
class ReasoningAgent(BaseAgent):
    name = "reasoning"
    def run(self, task):
        intent = str(task.get("intent", "general"))
        return AgentResult(self.name, "planned", "Use a task-appropriate reasoning strategy.", {
            "intent": intent,
            "checks": ["identify assumptions", "compare viable approaches", "resolve contradictions", "state uncertainty"],
            "decomposition_required": bool(task.get("deep", False)),
        }, ["This is orchestration guidance, not a generated solution or exposed private chain-of-thought."])

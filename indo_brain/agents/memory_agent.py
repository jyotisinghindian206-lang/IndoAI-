from .base import BaseAgent, AgentResult
class MemoryAgent(BaseAgent):
    name = "memory"
    def run(self, task):
        return AgentResult(self.name, "restricted", "Memory access is opt-in and account-scoped.", {
            "read_allowed": bool(task.get("memory_read_consent", False)),
            "write_allowed": bool(task.get("memory_write_consent", False)),
            "scope_required": True,
        }, ["This agent never reads or writes persistent memory on its own."])

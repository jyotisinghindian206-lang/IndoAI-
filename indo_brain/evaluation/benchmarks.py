"""Deterministic architecture smoke checks; not a general intelligence score."""
from ..reasoning.planner import create_reasoning_plan

def run_reasoning_smoke_benchmarks():
    cases=[("research", "Research latest AI safety standards", "Research"),
           ("coding", "Debug this Python API", "Coding"),
           ("math", "Calculate 13 times 17", "New Chat"),
           ("education", "Explain photosynthesis", "Study")]
    results=[]
    for expected, message, mode in cases:
        plan=create_reasoning_plan(message,mode)
        actual=plan.get("intent")
        results.append({"expected":expected,"actual":actual,"passed":actual==expected})
    return {"passed":sum(x["passed"] for x in results),"total":len(results),"cases":results,
            "note":"Intent-routing smoke test only; not a measure of factual accuracy or general intelligence."}

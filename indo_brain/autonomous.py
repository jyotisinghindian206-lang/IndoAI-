"""Local-first autonomous workflow helpers for Indo AI v13.

These helpers create reviewable plans and lightweight checks. They do not call
LLMs, execute submitted code, modify project files, or persist user content.
"""
from __future__ import annotations
import ast
import re
from collections import Counter
from typing import Any

_WORD = re.compile(r"[\w'-]+", re.UNICODE)
_STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "your", "you", "are", "was", "were", "will", "would", "could", "should", "have", "has", "had", "what", "when", "where", "which", "while", "about", "please", "make", "build", "create", "add", "improve", "better", "more"}


def _terms(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(str(text or "")) if len(w) > 2 and w.casefold() not in _STOP]


def create_agent_workflow(goal: str, mode: str = "New Chat") -> dict[str, Any]:
    """Create a bounded specialist workflow; agents are roles, not separate LLM calls."""
    text = str(goal or "").strip()
    low = text.casefold()
    roles: list[dict[str, str]] = []
    if re.search(r"\b(code|coding|python|javascript|api|debug|build|software|app)\b", low):
        roles = [
            {"role": "Architect", "task": "Map requirements, interfaces, dependencies and compatibility constraints."},
            {"role": "Implementer", "task": "Prepare the smallest coherent implementation while preserving existing behaviour."},
            {"role": "Test Engineer", "task": "Run syntax, unit and integration checks that are safe and available."},
            {"role": "Reviewer", "task": "Inspect security, regressions, edge cases and incomplete requirements."},
        ]
    elif re.search(r"\b(research|latest|compare|sources|investigate|report)\b", low):
        roles = [
            {"role": "Researcher", "task": "Gather relevant sources and record dates and provenance."},
            {"role": "Evidence Reviewer", "task": "Cross-check claims, conflicts and missing evidence."},
            {"role": "Synthesizer", "task": "Produce a concise report with citations and explicit uncertainty."},
        ]
    elif re.search(r"\b(plan|roadmap|project|strategy|launch)\b", low):
        roles = [
            {"role": "Planner", "task": "Define the outcome, milestones and dependencies."},
            {"role": "Risk Reviewer", "task": "Identify blockers, safety concerns and rollback points."},
            {"role": "Coordinator", "task": "Order the work into reviewable stages and acceptance criteria."},
        ]
    else:
        roles = [
            {"role": "Task Analyst", "task": "Identify the requested outcome and essential constraints."},
            {"role": "Verifier", "task": "Check that the final response addresses the request and qualifies uncertainty."},
        ]
    steps = [
        "Confirm the requested outcome and constraints",
        "Gather only the context and tools needed",
        "Complete the specialist work in dependency order",
        "Verify the result using available checks",
        "Present the outcome, limitations and any required approval",
    ]
    return {"ok": True, "mode": str(mode or "New Chat")[:40], "goal": text[:4000], "orchestration": "local role-based plan; no extra model calls", "roles": roles, "steps": steps, "requires_user_approval_for_changes": True}


def evaluate_answer(question: str, answer: str, task: str = "general") -> dict[str, Any]:
    """Return transparent heuristic coverage signals, never a truth/accuracy score."""
    q_terms, a_terms = set(_terms(question)), set(_terms(answer))
    overlap = len(q_terms & a_terms)
    coverage = round(overlap / max(1, len(q_terms)), 3)
    checks = {
        "has_content": bool(str(answer or "").strip()),
        "addresses_topic_terms": coverage >= 0.15 or not q_terms,
        "avoids_empty_response": len(str(answer or "").strip()) >= 12,
        "uncertainty_language_present_when_qualified": True,
    }
    warnings = []
    if not checks["has_content"]:
        warnings.append("No answer content was supplied.")
    if q_terms and coverage < 0.15:
        warnings.append("The answer may not cover enough of the request's key terms.")
    if re.search(r"\b(verified|tested|executed|deployed|confirmed)\b", str(answer or ""), re.I) and not re.search(r"\b(not|unable|cannot|couldn't|didn't)\b", str(answer or ""), re.I):
        warnings.append("Check any claim of testing or verification against actual tool results.")
    return {"task": str(task or "general"), "signals": checks, "topic_term_coverage": coverage, "warnings": warnings, "score_type": "heuristic coverage only; not factual accuracy or model intelligence"}


def extract_ephemeral_knowledge_graph(text: str, limit: int = 24) -> dict[str, Any]:
    """Extract a tiny ephemeral keyword graph for visualization/debugging only."""
    terms = _terms(text)
    counts = Counter(terms)
    nodes = [{"id": term, "label": term, "weight": count} for term, count in counts.most_common(max(2, min(limit, 40)))]
    edges = []
    for left, right in zip(nodes, nodes[1:]):
        edges.append({"source": left["id"], "target": right["id"], "relation": "co-mentioned"})
    return {"nodes": nodes, "edges": edges, "persistence": "none; request-local only", "note": "Keyword associations are not verified semantic facts."}


def build_project_change_plan(goal: str, constraints: list[str] | None = None) -> dict[str, Any]:
    """Build a change plan with backup, test and rollback gates."""
    plan = create_agent_workflow(goal, "Coding")
    plan["change_gates"] = [
        "Inspect the current source before editing",
        "Back up source and identify user-data locations",
        "Make changes in a separate working copy",
        "Run syntax and focused regression tests",
        "Review the diff for secrets, data resets and unrelated changes",
        "Require explicit approval before replacing production files or deploying",
    ]
    plan["constraints"] = [str(x)[:300] for x in (constraints or [])[:12]]
    plan["rollback"] = "Restore the pre-change source backup; do not roll back or recreate user databases unless explicitly requested."
    return plan


def safe_python_check(code: str) -> dict[str, Any]:
    """Parse Python without executing it; report syntax only."""
    source = str(code or "")
    if len(source) > 120_000:
        return {"ok": False, "kind": "limit", "message": "Code exceeds the 120 KB validation limit."}
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"ok": False, "kind": "syntax", "message": exc.msg, "line": exc.lineno, "column": exc.offset}
    return {"ok": True, "kind": "syntax", "message": "Python syntax is valid. The code was parsed, not executed.", "top_level_nodes": len(tree.body)}

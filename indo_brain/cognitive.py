"""Deterministic local cognitive planning for Indo AI v11.0.

This module does not call a model, access the network, or mutate user memory.
It selects a response strategy and context budget from the current request.
"""
from __future__ import annotations
import hashlib
import re
from typing import Any

_WORD = re.compile(r"[\w'-]+", re.UNICODE)

_SYNONYMS = {
    "code": {"code", "coding", "program", "programming", "script", "developer", "debug"},
    "music": {"music", "song", "songs", "track", "tracks", "audio", "playlist", "singer"},
    "login": {"login", "signin", "sign-in", "oauth", "google", "authentication", "session"},
    "memory": {"memory", "remember", "remembering", "history", "persistent", "persistence", "saved"},
    "image": {"image", "picture", "photo", "visual", "diagram", "illustration", "screenshot"},
    "school": {"school", "homework", "chapter", "class", "lesson", "study", "exam"},
    "deploy": {"deploy", "deployment", "render", "hosting", "production", "server"},
}

_COMPLEX = re.compile(r"\b(architecture|production|complete|entire|integrate|integration|refactor|migrate|debug|traceback|security|performance|benchmark|comprehensive|step.by.step|compare|research|sources|citations|multiple|all features|end.to.end|system design|memory architecture|large language model|llm|ai assistant|microservices|authentication|oauth)\b", re.I)
_CODE = re.compile(r"\b(code|coding|python|javascript|fastapi|api|function|class|bug|error|traceback|debug|deploy|database|sql|html|css|react|typescript|llm|large language model|ai assistant|architecture|system design|memory architecture|backend|authentication|oauth|integration|integrate|scalable|microservice|microservices|software design|technical design)\b", re.I)
_RESEARCH = re.compile(r"\b(latest|today|current|recent|research|sources|citations|news|price|weather|schedule|202[5-9])\b", re.I)
_MATH = re.compile(r"\b(calculate|solve|equation|formula|integral|derivative|probability|percentage|area|volume|convert)\b", re.I)


def _expanded_terms(text: str) -> set[str]:
    words = {x.casefold() for x in _WORD.findall(str(text or "")) if len(x) > 2}
    expanded = set(words)
    for group in _SYNONYMS.values():
        if words & group:
            expanded.update(group)
    return expanded


def analyze_request(message: str, mode: str = "New Chat", attachment_count: int = 0) -> dict[str, Any]:
    """Create an explainable, local-only task and reasoning plan.

    This is a routing heuristic, not model reasoning and not a guarantee of
    accuracy. It makes no network/API calls and never writes user memory.
    """
    text = str(message or "").strip()
    lower = text.casefold()
    words = _WORD.findall(text)
    mode_lower = str(mode or "").casefold()
    task = "general"
    if re.fullmatch(r"(?:hi|hey|hello|wsp|sup|yo|thanks|thank you|bye|gn)[!. ]*", lower):
        task = "casual"
    elif re.search(r"\b(anxious|anxiety|sad|upset|overwhelmed|lonely|stressed|scared|hurt|not okay|not ok)\b", lower):
        task = "emotional_support"
    elif _CODE.search(text) or "coding" in mode_lower or mode_lower == "code":
        task = "coding"
    elif _RESEARCH.search(text) or any(x in mode_lower for x in ("research", "web")):
        task = "research"
    elif _MATH.search(text) or re.search(r"\d\s*[+*/=^-]\s*\d", text):
        task = "math_logic"
    elif re.search(r"\b(compare|comparison|versus|\bvs\b|pros and cons)\b", lower):
        task = "comparison"
    elif re.search(r"\b(explain|teach|learn|photosynthesis|chapter|homework|class \d)\b", lower) or "study" in mode_lower:
        task = "education"
    elif re.search(r"\b(plan|roadmap|strategy|steps|schedule|how should i|how can i)\b", lower):
        task = "planning"
    elif re.search(r"\b(write|story|poem|caption|design|brainstorm|imagine)\b", lower):
        task = "creative"

    attachment_count = min(max(int(attachment_count or 0), 0), 10)
    signals = []
    score = 0
    if len(words) >= 18:
        points = min(len(words) // 18, 3); score += points; signals.append("request_length")
    if _COMPLEX.search(text):
        score += 2; signals.append("technical_or_multi_step_terms")
    if task in {"coding", "research", "math_logic"}:
        score += 2; signals.append("precision_sensitive_task")
    if attachment_count:
        score += min(1 + attachment_count, 3); signals.append("attachments")
    if len(re.findall(r"\n", text)) >= 3:
        score += 1; signals.append("structured_input")
    if len(re.findall(r"[?]", text)) >= 3:
        score += 1; signals.append("multiple_questions")
    if len(re.findall(r"\b(?:and|also|plus|additionally|include|preserve|without|while)\b", lower)) >= 3:
        score += 1; signals.append("multiple_constraints")
    if re.search(r"\b(?:all|every|entire|complete|end.to.end|full project|existing features)\b", lower):
        score += 1; signals.append("broad_scope")
    score = min(score, 10)

    explicit_brief = bool(re.search(r"\b(?:briefly|short answer|just the answer|answer only|no explanation)\b", lower))
    if task == "casual" or (task == "general" and score <= 1):
        tier, history_messages, history_chars, memory_chars = "quick", 3, 1600, 900
    elif score >= 5 or task in {"coding", "research", "math_logic"}:
        tier, history_messages, history_chars, memory_chars = "deep", 10, 9000, 1800
    else:
        tier, history_messages, history_chars, memory_chars = "standard", 7, 6000, 1400

    # A brevity request changes output length, not the care needed for correctness.
    response_length = "concise" if explicit_brief else ("expanded" if score >= 6 else "balanced")
    structure = {
        "casual": "direct conversational reply",
        "coding": "implementation, integration, edge cases, validation and compatibility",
        "research": "findings, evidence, dates, source quality and uncertainty",
        "math_logic": "method, calculation, units and independent check",
        "comparison": "decision criteria, compact comparison and trade-offs",
        "education": "clear explanation, concrete example, recap and useful visual if warranted",
        "emotional_support": "empathetic response, reflect the actual concern and optional gentle next step",
        "planning": "goal, ordered steps, dependencies, risks and milestones",
        "creative": "deliver the requested creative artifact in the requested style",
        "general": "direct answer with only useful supporting context",
    }.get(task, "direct answer")
    checks = {
        "coding": ["requirements covered", "existing interfaces preserved", "imports and integration complete", "security and edge cases considered", "tests reported honestly"],
        "research": ["claims match retrieved sources", "dates and source quality checked", "conflicts and uncertainty disclosed", "citations are real"],
        "math_logic": ["method valid", "arithmetic independently checked", "units and final result consistent"],
        "education": ["level appropriate", "key terms explained", "example supports the concept", "no unnecessary complexity"],
        "comparison": ["same criteria used", "missing data identified", "trade-offs explained"],
        "planning": ["steps ordered", "dependencies identified", "risks and realistic constraints included"],
    }.get(task, ["request fully addressed", "claims appropriately qualified", "answer length proportional to task"])
    return {
        "task": task, "complexity": score, "tier": tier,
        "response_length": response_length,
        "history_messages": history_messages, "history_chars": history_chars,
        "memory_chars": memory_chars, "structure": structure,
        "attachment_count": attachment_count, "complexity_signals": signals,
        "quality_checks": checks,
    }


def cognitive_guidance(plan: dict[str, Any]) -> str:
    task = plan.get("task", "general")
    tier = plan.get("tier", "standard")
    structure = plan.get("structure", "direct answer")
    checks = plan.get("quality_checks", [])
    checks_text = "; ".join(str(x) for x in checks[:6])
    return (
        f"COGNITIVE RESPONSE PLAN (local heuristic; do not reveal): task={task}; tier={tier}; "
        f"complexity={plan.get('complexity', 0)}/10; output_length={plan.get('response_length', 'balanced')}. "
        f"Preferred structure: {structure}. Apply these task-specific quality checks: {checks_text}. "
        "Use quick depth for simple tasks, standard depth for ordinary multi-part tasks, and deeper context/verification for complex or precision-sensitive tasks. "
        "A brevity request controls length, not correctness. This plan is a heuristic, not evidence that a task was completed or verified. "
        "If the request is ambiguous, ask one essential clarification. For current facts, use live retrieval when available; never simulate browsing. "
        "For claims requiring evidence, separate verified facts from inference. Add a diagram, chart or image only when it improves comprehension; "
        "never fabricate data, citations, URLs or image results."
    )


def request_fingerprint(message: str, mode: str = "New Chat") -> str:
    """Stable, non-reversible request key for local diagnostics/cache bucketing."""
    normalized = re.sub(r"\s+", " ", str(message or "").strip().casefold())
    payload = (str(mode or "New Chat").strip().casefold() + "\0" + normalized).encode("utf-8", "ignore")
    return hashlib.sha256(payload).hexdigest()[:20]


def adaptive_history(history: list[dict[str, str]], plan: dict[str, Any]) -> list[dict[str, str]]:
    """Apply the planner's bounded context budget to already-compressed history."""
    max_messages = int(plan.get("history_messages", 7))
    max_chars = int(plan.get("history_chars", 6000))
    selected = list(history or [])[-max_messages:]
    out: list[dict[str, str]] = []
    used = 0
    for item in selected:
        role = str(item.get("role", "user"))[:20]
        content = str(item.get("content", ""))
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:max(0, remaining - 1)].rstrip() + "…"
        if content:
            out.append({"role": role, "content": content})
            used += len(content) + len(role) + 8
    return out

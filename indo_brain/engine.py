"""Local-first Brain Engine for Indo AI.

No LLM/API call is made here. The module uses bounded, deterministic processing
so it can reduce prompt size without adding provider spend or hidden latency.
"""
from __future__ import annotations
import re
from typing import Any, Iterable

_WORD = re.compile(r"[\w'-]+", re.UNICODE)
_STOP = {"the","a","an","and","or","but","is","are","was","were","be","to","of","in","on","for","with","it","this","that","i","you","we","they","he","she","my","your","our","me","do","does","did","can","could","would","should","what","how","why","when","where","who","please","explain","tell","give","make","show"}


def _terms(text: str) -> set[str]:
    words = {w.casefold() for w in _WORD.findall(str(text or "")) if len(w) > 2 and w.casefold() not in _STOP}
    # Expand common project vocabulary so related terms can retrieve relevant memory.
    synonym_groups = (
        {"code", "coding", "program", "programming", "script", "developer", "debug"},
        {"music", "song", "songs", "track", "tracks", "audio", "playlist"},
        {"login", "signin", "oauth", "google", "authentication", "session"},
        {"memory", "remember", "history", "persistent", "persistence", "saved"},
        {"image", "picture", "photo", "visual", "diagram", "screenshot"},
        {"deploy", "deployment", "render", "hosting", "production", "server"},
    )
    expanded = set(words)
    for group in synonym_groups:
        if words & group:
            expanded.update(group)
    return expanded


def classify_task(message: str, mode: str = "New Chat") -> str:
    q = str(message or "").strip().casefold()
    m = str(mode or "").casefold()
    if re.fullmatch(r"(?:hi|hey|hello|wsp|sup|yo|thanks|thank you|bye|gn|good night)[!. ]*", q):
        return "casual"
    if re.search(r"\b(depressed|depression|anxious|anxiety|overwhelmed|lonely|sad|upset|stressed|scared|hurt|feel low|feeling low|not okay|not ok)\b", q):
        return "emotional_support"
    if any(x in m for x in ("coding", "code")) or re.search(r"\b(code|python|javascript|fastapi|debug|traceback|refactor|implement|api|function|script|program|compile|bug)\b", q):
        return "coding"
    if any(x in m for x in ("research", "web")) or re.search(r"\b(latest|today|current|news|research|sources|verify|citation|recent)\b", q):
        return "research"
    if re.search(r"\b(compare|comparison|difference|versus|vs\.?|pros and cons)\b", q):
        return "comparison"
    if any(x in m for x in ("study", "learning", "education")) or re.search(r"\b(explain|teach|learn|how does|how do|why does|photosynthesis|chlorophyll|diagram|chapter|class \d|homework)\b", q):
        return "education"
    if re.search(r"\b(plan|steps|schedule|roadmap|strategy|how can i|how should i)\b", q):
        return "practical_guidance"
    if re.search(r"\b(write|story|poem|caption|design|brainstorm|creative|imagine)\b", q):
        return "creative"
    return "general"


def _clean(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + "…"


def _rank_sentences(text: str, query_terms: set[str], limit: int = 2) -> str:
    raw = re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
    scored = []
    for index, sentence in enumerate(raw):
        sentence = _clean(sentence, 320)
        terms = _terms(sentence)
        if len(sentence) < 12:
            continue
        score = len(terms & query_terms) * 3 + min(len(terms), 18) * .04
        if re.search(r"\b(important|prefer|goal|project|using|needs|avoid|always|never|class|level)\b", sentence, re.I):
            score += .5
        scored.append((score, -index, sentence))
    if not scored:
        return _clean(text, 180)
    chosen = sorted(scored, reverse=True)[:limit]
    return " ".join(x[2] for x in sorted(chosen, key=lambda x: -x[1]))


def compress_history(history: Iterable[Any], current_message: str, mode: str = "New Chat",
                     max_messages: int = 8, max_chars: int = 9000) -> list[dict[str, str]]:
    """Keep the latest turns verbatim and extractively condense older turns."""
    items = list(history or [])
    if items and _clean(getattr(items[-1], "content", items[-1].get("content", "") if isinstance(items[-1], dict) else ""), 5000) == _clean(current_message, 5000):
        items = items[:-1]
    if not items:
        return []
    query_terms = _terms(current_message)
    deep = str(mode or "").casefold() in {"coding", "code", "research", "web research", "web"}
    recent_keep = 5 if deep else 4
    selected = items[-max_messages:]
    split = max(0, len(selected) - recent_keep)
    output: list[dict[str, str]] = []
    used = 0
    for index, item in enumerate(selected):
        role = str(getattr(item, "role", item.get("role", "user") if isinstance(item, dict) else "user") or "user")[:20]
        content = str(getattr(item, "content", item.get("content", "") if isinstance(item, dict) else "") or "")
        if index < split:
            # Old turns are compacted into their most query-relevant sentences.
            compact = _rank_sentences(content, query_terms, 1 if not deep else 2)
            content = "[Earlier context] " + compact
        else:
            content = _clean(content, 1800 if deep else 1250)
        remaining = max_chars - used
        if remaining <= 0:
            break
        content = _clean(content, remaining)
        if content:
            output.append({"role": role, "content": content})
            used += len(content) + len(role) + 8
    return output


def filter_memory_context(context: str, current_message: str, max_chars: int = 1400) -> str:
    """Select relevant lines from the already-authorized per-account memory only."""
    raw = str(context or "").strip()
    if not raw:
        return ""
    query = _terms(current_message)
    q = str(current_message or "").casefold()
    emotional = bool(re.search(r"\b(depressed|depression|anxious|anxiety|overwhelmed|lonely|sad|upset|stressed|scared|hurt|feel low|feeling low)\b", q))
    lines = [re.sub(r"\s+", " ", x).strip() for x in raw.splitlines() if x.strip()]
    ranked = []
    for i, line in enumerate(lines):
        terms = _terms(line)
        overlap = len(query & terms)
        score = overlap * 3
        if emotional and re.search(r"\b(emotion|support|stress|anx|sad|low|mental|feel|overwhelm|comfort|sensitive)\w*\b", line, re.I):
            score += 5
        if re.search(r"\b(prefer|goal|project|class|learning|language|style|avoid)\b", line, re.I):
            score += 1
        # Preserve short section labels only when a useful line under them survives.
        ranked.append((score, -i, line))
    if not query:
        chosen = [x[2] for x in ranked[:5]]
    else:
        useful = [x for x in ranked if x[0] > 0]
        if not useful:
            return ""
        chosen = [x[2] for x in sorted(useful, reverse=True)[:8]]
        chosen.reverse()
    result = "\n".join(chosen)
    return _clean(result, max_chars)


def answer_guidance(task: str, visual_answers: bool = True) -> str:
    common = (
        "Answer the user's explicit request first. Add only high-value context that makes the answer easier to understand or act on; "
        "do not pad, overwhelm, invent follow-up needs, or repeat the same point. Keep simple greetings and simple factual answers short. "
        "Offer one useful next step only when it genuinely helps."
    )
    guidance = {
        "casual": "Keep this natural, brief and conversational. Do not turn small talk into a lesson or checklist.",
        "emotional_support": "Lead with empathy and respond to the person's actual words. Do not diagnose, over-interpret, force advice, or turn the moment into productivity coaching. Ask at most one gentle question when needed.",
        "education": "Teach in layers: clear explanation, a concrete example, and a small recap. Add a compact table, labeled text diagram or Mermaid flowchart when it materially clarifies the concept. Match the user's stated level.",
        "comparison": "Use a compact comparison table when it improves scanning; explain the most decision-relevant differences and note uncertainty or missing specs.",
        "coding": "Prioritize a complete, compatible implementation, integration details, edge cases and validation. Do not add unrelated tutorials or decorative visuals. Preserve existing interfaces and features.",
        "research": "Separate verified facts from inference. Use only retrieved sources for current claims; include dates and source links when supplied. Do not invent images, citations or live verification.",
        "practical_guidance": "Give a realistic sequence, dependencies and likely pitfalls. Keep the plan actionable and avoid adding unrelated goals.",
        "creative": "Honor the requested style and deliver the artifact directly. Add alternatives only when requested or clearly useful.",
        "general": "Choose the clearest format for the task. Use examples, bullets, tables or a diagram only when they materially improve understanding.",
    }.get(task, "Choose the clearest format for the task.")
    visual = ("Visual enrichment: when a diagram or chart materially helps, use a supported Mermaid flowchart, a Markdown table, or a chart only from real supplied/retrieved numeric data. Use actual available image assets only; never fabricate image URLs or claim an image was fetched/generated. Do not force visuals into every answer."
              if visual_answers else "Do not add optional visual enrichment; answer in clear text unless the user explicitly requests a visual.")
    return common + "\n" + guidance + "\n" + visual


def estimate_tokens(text: str) -> int:
    """Conservative rough estimate only; exact provider tokenization is model-specific."""
    value = str(text or "")
    return max(1, (len(value) + 3) // 4) if value else 0


def build_context_plan(message: str, mode: str, history: Iterable[Any], memory: str,
                       visual_answers: bool = True, attachment_count: int = 0) -> dict[str, Any]:
    """Build a bounded, local-only response plan with adaptive context budgets."""
    from .cognitive import analyze_request, cognitive_guidance, adaptive_history, request_fingerprint

    cognitive = analyze_request(message, mode, attachment_count)
    # Compress older history first, then allocate the remaining context by task complexity.
    compact_history = compress_history(
        history, message, mode,
        max_messages=max(8, int(cognitive["history_messages"]) + 2),
        max_chars=max(9000, int(cognitive["history_chars"]) + 3000),
    )
    compact_history = adaptive_history(compact_history, cognitive)
    relevant_memory = filter_memory_context(
        memory, message, max_chars=int(cognitive["memory_chars"])
    )
    history_text = "\n".join(f"{x['role'].upper()}: {x['content']}" for x in compact_history)
    task = classify_task(message, mode)
    guidance = answer_guidance(task, visual_answers) + "\n" + cognitive_guidance(cognitive)
    return {
        "task": task,
        "history": compact_history,
        "history_text": history_text,
        "memory": relevant_memory,
        "guidance": guidance,
        "cognitive": cognitive,
        "request_fingerprint": request_fingerprint(message, mode),
        "estimated_context_tokens": estimate_tokens(history_text + "\n" + relevant_memory + "\n" + str(message or "")),
    }

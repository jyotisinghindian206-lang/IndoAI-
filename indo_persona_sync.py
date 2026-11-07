"""Adaptive Persona Sync for Indo AI.

Learns only explicit, non-sensitive communication preferences. Momentary tone and
format cues are applied to the current turn only; they are never persisted as facts.
All persistent preferences are stored in account-scoped encrypted DLM.
"""
from __future__ import annotations
import re
from typing import Any

_RULES = (
    (re.compile(r"\b(keep it short|be concise|short answers|brief replies|don't make it long|dont make it long|no long explanations)\b", re.I), "Prefer concise answers unless the user asks for detail."),
    (re.compile(r"\b(explain in detail|go in depth|more detailed|deep explanations|don't skip steps|dont skip steps)\b", re.I), "Prefer thorough explanations with the important steps included."),
    (re.compile(r"\b(one by one|step by step|one step at a time)\b", re.I), "For multi-step work, present and complete one step at a time."),
    (re.compile(r"\b(no emojis|don't use emojis|dont use emojis)\b", re.I), "Avoid emojis unless explicitly requested."),
    (re.compile(r"\b(use hinglish|reply in hinglish|hinglish please)\b", re.I), "Use natural Hinglish when appropriate."),
    (re.compile(r"\b(use english|reply in english|english only)\b", re.I), "Reply in English unless the user requests another language."),
    (re.compile(r"\b(respectful|formal tone|professional tone)\b", re.I), "Keep the tone respectful and polished."),
    (re.compile(r"\b(casual tone|talk casually|casual style)\b", re.I), "Use a relaxed, conversational tone when the topic allows."),
)


def explicit_preference(message: str) -> str | None:
    text = str(message or "")[:2000]
    # Require a clear preference instruction, not a passing descriptive mention.
    if not re.search(r"\b(please|always|from now|going forward|i prefer|i want you to|keep|use|don't|dont|avoid|reply|answer|explain)\b", text, re.I):
        return None
    for pattern, rule in _RULES:
        if pattern.search(text):
            return rule
    return None


def current_turn_style(message: str) -> str:
    text = str(message or "")
    rules = []
    if len(text) < 45 and re.search(r"\b(quick|just tell me|short answer|briefly)\b", text, re.I):
        rules.append("For this turn, answer briefly and directly.")
    if re.search(r"\b(explain|teach|how does|why does|step by step)\b", text, re.I):
        rules.append("For this turn, explain the reasoning clearly at the level requested.")
    if re.search(r"\b(code|debug|implement|build|fix|architecture)\b", text, re.I):
        rules.append("For this turn, prioritize technically complete, integrated, testable work.")
    if re.search(r"\b(wsp|yo|sup|bro|bhai)\b", text, re.I) and len(text) < 180:
        rules.append("A relaxed conversational tone is appropriate for this turn; do not force slang into technical details.")
    return "\n".join(rules)


def sync_profile(dlm: Any, identity: str, message: str, *, limit: int = 8) -> str:
    """Save an explicit preference and return the account's compact style profile."""
    if not dlm or not identity:
        return current_turn_style(message)
    try:
        rule = explicit_preference(message)
        if rule:
            # Replace the previous persona-sync preference set before saving the new
            # explicit instruction; prevents old and new preferences contradicting.
            try:
                for old_item in dlm.list_all(identity, limit=160):
                    if (str(old_item.get("source", "")) == "persona_sync"
                            and str(old_item.get("category", "")) == "preference"
                            and old_item.get("id")):
                        dlm.delete(identity, memory_id=str(old_item["id"]))
            except Exception:
                pass
            # DLM encrypts and scopes this to the authenticated account.
            dlm.save(identity, rule, category="preference", scope="account",
                     confidence=.98, importance=.62, source="persona_sync")
        memories = dlm.list_all(identity, limit=160)
        preferences = []
        for item in memories:
            if str(item.get("source", "")) == "persona_sync" and str(item.get("category", "")) == "preference":
                value = re.sub(r"\s+", " ", str(item.get("text", "") or item.get("content", ""))).strip()
                if value and value not in preferences:
                    preferences.append(value[:220])
                if len(preferences) >= limit:
                    break
        dynamic = current_turn_style(message)
        sections = []
        if preferences:
            sections.append("ADAPTIVE PERSONA SYNC — explicit account preferences:\n" + "\n".join("- " + p for p in preferences))
        if dynamic:
            sections.append("CURRENT-TURN STYLE (temporary; do not save as a lasting preference):\n" + dynamic)
        return "\n\n".join(sections)
    except Exception as exc:
        print("[Indo persona sync warning]", type(exc).__name__)
        return current_turn_style(message)

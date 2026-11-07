"""Opt-in Devil's Advocate reasoning mode for Indo AI.

This module only builds prompt guidance; it performs no network calls, tools,
external actions, or persistent memory writes.
"""
from __future__ import annotations
import re

_MODE_NAMES = {"devil's advocate", "devils advocate", "challenge", "critical review", "red team"}
_TRIGGER = re.compile(
    r"\b(?:devil'?s advocate|challenge my (?:idea|plan|assumption|argument)|"
    r"stress[- ]test (?:this|my)|critically challenge|argue against (?:this|me)|"
    r"red[- ]team (?:this|my))\b", re.I
)


def enabled(message: str, mode: str = "") -> bool:
    """Enable only when explicitly selected or requested for this turn."""
    selected = re.sub(r"\s+", " ", str(mode or "").strip().casefold())
    return selected in _MODE_NAMES or bool(_TRIGGER.search(str(message or "")))


def build_guidance(message: str, mode: str = "") -> str:
    """Return concise, evidence-aware critical-thinking instructions."""
    if not enabled(message, mode):
        return ""
    return """\nDEVIL'S ADVOCATE MODE — ACTIVE FOR THIS TURN
Act as a rigorous, fair-minded critic of the proposal or claim the user presents.
1. Identify the central claim and the assumptions it depends on.
2. Present the strongest reasonable counterargument, not a straw man.
3. Test feasibility, evidence quality, hidden costs, edge cases, incentives, and failure modes.
4. Separate verified facts, reasonable inferences, and speculation; never invent evidence or citations.
5. Consider what evidence would change the assessment and what would strengthen the proposal.
6. End with a balanced verdict: strongest point, biggest weakness, and a practical improvement or test.
Be direct but respectful. Do not disagree merely for performance, and do not treat this mode as permission to provide unsafe instructions. If the proposal is already sound, say so and explain why. This mode changes analysis style, not the user's requested output format."""

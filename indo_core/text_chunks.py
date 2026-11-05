"""Predictable text chunking for streaming, TTS, and provider context budgets."""
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    start: int
    end: int

class TextChunker:
    def __init__(self, max_chars: int = 2_000, overlap_chars: int = 0):
        if max_chars < 32:
            raise ValueError("max_chars must be at least 32")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be in [0, max_chars)")
        self.max_chars = int(max_chars)
        self.overlap_chars = int(overlap_chars)

    def split(self, text: str) -> list[TextChunk]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if not text:
            return []
        chunks: list[TextChunk] = []
        cursor = 0
        length = len(text)
        while cursor < length:
            hard_end = min(length, cursor + self.max_chars)
            end = hard_end
            if hard_end < length:
                # Prefer paragraph, sentence, then word boundaries without creating tiny chunks.
                floor = cursor + max(24, self.max_chars // 2)
                candidates = [text.rfind("\n\n", cursor, hard_end),
                              text.rfind(". ", cursor, hard_end),
                              text.rfind("! ", cursor, hard_end),
                              text.rfind("? ", cursor, hard_end),
                              text.rfind(" ", cursor, hard_end)]
                usable = [point + (2 if text[point:point+2] in {"\n\n", ". ", "! ", "? "} else 1)
                          for point in candidates if point >= floor]
                if usable:
                    end = max(usable)
            if end <= cursor:
                end = hard_end
            piece = text[cursor:end].strip()
            if piece:
                # Track the source window, including trimmed boundary whitespace.
                chunks.append(TextChunk(len(chunks), piece, cursor, end))
            if end >= length:
                break
            cursor = max(cursor + 1, end - self.overlap_chars)
        return chunks


def estimate_tokens(text: str) -> int:
    """Rough conservative token estimate for UI budgeting, not billing."""
    if not text:
        return 0
    # Mixed scripts and punctuation vary by tokenizer; this is only a rough guardrail.
    words = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, int(len(words) * 1.25))


def trim_history(messages: list[dict], max_tokens: int, preserve_latest: int = 2) -> list[dict]:
    """Keep recent messages under an approximate budget, always preserving latest N."""
    if max_tokens < 1:
        return []
    clean = [m for m in messages if isinstance(m, dict) and isinstance(m.get("content"), str)]
    if not clean:
        return []
    pinned_count = min(max(0, preserve_latest), len(clean))
    pinned = clean[-pinned_count:] if pinned_count else []
    pinned_ids = set(id(m) for m in pinned)
    budget = max(0, max_tokens - sum(estimate_tokens(m["content"]) for m in pinned))
    kept = []
    for message in reversed(clean[:-pinned_count] if pinned_count else clean):
        cost = estimate_tokens(message["content"])
        if cost <= budget:
            kept.append(message)
            budget -= cost
    kept.reverse()
    return kept + pinned

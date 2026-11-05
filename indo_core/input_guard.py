"""Defensive request-text checks. These checks are not a replacement for auth."""
from __future__ import annotations
from dataclasses import dataclass
import unicodedata
from typing import Iterable

@dataclass(frozen=True)
class GuardResult:
    accepted: bool
    text: str
    reasons: tuple[str, ...] = ()
    normalized_length: int = 0

class InputGuard:
    def __init__(self, max_chars: int = 20_000, max_lines: int = 2_000,
                 allow_empty: bool = False, strip_control_chars: bool = True):
        self.max_chars = max(1, int(max_chars))
        self.max_lines = max(1, int(max_lines))
        self.allow_empty = allow_empty
        self.strip_control_chars = strip_control_chars

    def normalize(self, value: object) -> str:
        text = unicodedata.normalize("NFC", str(value if value is not None else ""))
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if self.strip_control_chars:
            text = "".join(ch for ch in text if ch in "\n\t" or not unicodedata.category(ch).startswith("C"))
        return text.strip()

    def check(self, value: object) -> GuardResult:
        text = self.normalize(value)
        reasons: list[str] = []
        if not text and not self.allow_empty:
            reasons.append("empty")
        if len(text) > self.max_chars:
            reasons.append("too_long")
        if text.count("\n") + 1 > self.max_lines:
            reasons.append("too_many_lines")
        return GuardResult(not reasons, text, tuple(reasons), len(text))

    def check_many(self, values: Iterable[object]) -> list[GuardResult]:
        return [self.check(value) for value in values]

    @staticmethod
    def redact_common_secrets(text: str) -> str:
        """Best-effort redaction for logs; never use as a substitute for secret storage."""
        import re
        patterns = [
            (r"(?i)\b(api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]"),
            (r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_API_KEY]"),
            (r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED_API_KEY]"),
        ]
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        return result

    @staticmethod
    def has_suspicious_path(value: str) -> bool:
        """Flag path traversal indicators; caller must still enforce a safe base path."""
        normalized = value.replace("\\", "/")
        return ".." in normalized.split("/") or normalized.startswith("/") or "\x00" in value

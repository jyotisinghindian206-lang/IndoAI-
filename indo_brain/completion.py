"""Provider-neutral helpers for detecting and safely joining truncated generations."""

import os
import re

CONTINUATION_INSTRUCTION = (
    "Continue the previous answer from the exact point where it stopped. "
    "Do not repeat, summarize, or restart any text already written. "
    "Preserve the existing structure, table rows, code blocks, numbering, and tone. "
    "Finish every remaining requested part, and end with a complete sentence."
)


def configured_continuation_limit(value=None):
    """Return a bounded number of continuation attempts (default: two)."""
    raw = os.getenv("INDO_MAX_CONTINUATIONS", "2") if value is None else value
    try:
        return max(0, min(int(raw), 3))
    except (TypeError, ValueError):
        return 2


def finish_reason_name(value):
    """Normalize SDK enums and provider strings to a comparable finish reason."""
    if value is None:
        return ""
    name = getattr(value, "name", None)
    text = str(name if name is not None else value).strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def is_length_finish_reason(value):
    """True only for provider finish reasons that explicitly indicate token exhaustion."""
    reason = finish_reason_name(value)
    return reason in {"LENGTH", "MAX_TOKENS", "MAX_OUTPUT_TOKENS", "TOKEN_LIMIT"}


def trim_continuation_overlap(previous, continuation):
    """Remove repeated boundary text from a continuation without altering its remainder."""
    previous = str(previous or "")
    continuation = str(continuation or "")
    if not previous or not continuation:
        return continuation

    # Prefer the longest exact character overlap; this preserves punctuation/spacing.
    max_chars = min(len(previous), len(continuation), 8192)
    for size in range(max_chars, 7, -1):
        if previous[-size:].casefold() == continuation[:size].casefold():
            return continuation[size:]

    # Models sometimes repeat the same boundary phrase with different punctuation.
    # Token overlap also catches short cut points (e.g. previous ends in "mid",
    # continuation starts "mid-sentence"). Require a >=3-character token.
    prev_tail = previous[-6000:]
    next_head = continuation[:6000]
    prev_tokens = list(re.finditer(r"[\w']+", prev_tail, flags=re.UNICODE))
    next_tokens = list(re.finditer(r"[\w']+", next_head, flags=re.UNICODE))
    limit = min(len(prev_tokens), len(next_tokens), 80)
    for count in range(limit, 0, -1):
        left = [m.group(0).casefold() for m in prev_tokens[-count:]]
        right = [m.group(0).casefold() for m in next_tokens[:count]]
        if left == right and sum(len(x) for x in left) >= 3:
            return continuation[next_tokens[count - 1].end():]
    if previous[-1].isalnum() and continuation[0].isalnum():
        return " " + continuation
    return continuation


# Strong end-of-stream signals only. This is deliberately conservative: a model
# can legitimately finish on a heading, code block, list item, or short phrase.
_INCOMPLETE_ENDING = re.compile(
    r"(?:\b(?:and|or|but|because|since|although|though|which|that|with|without|to|of|for|from|the|a|an|is|are|was|were|will|would|could|should|if|when|while|including|such as)\s*|[,;:]|[—–-]|[([{])$",
    re.IGNORECASE,
)


def response_looks_truncated(text):
    """Detect a few high-confidence structural/linguistic truncation endings."""
    value = str(text or "").rstrip()
    if not value:
        return False
    # An unmatched Markdown fence is a strong signal for code-heavy responses.
    if value.count("```") % 2:
        return True
    # Do not treat ordinary final punctuation as incomplete.
    tail = value[-180:]
    if _INCOMPLETE_ENDING.search(tail):
        return True
    # A final opening delimiter is almost always an interrupted expression/list.
    if value[-1:] in ("(", "[", "{", "`", "\\"):
        return True
    return False


def should_continue_response(finish_reason, text):
    """Return true for explicit token exhaustion or a strong incomplete-tail signal."""
    return is_length_finish_reason(finish_reason) or response_looks_truncated(text)


def is_retryable_stream_error(exc):
    """Classify transient transport/server failures; never retry quota/auth failures."""
    import http.client
    import socket
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        return int(getattr(exc, "code", 0) or 0) in {408, 409, 425, 500, 502, 503, 504}
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionError,
                         ConnectionResetError, BrokenPipeError,
                         http.client.IncompleteRead, http.client.RemoteDisconnected,
                         urllib.error.URLError)):
        reason = getattr(exc, "reason", None)
        if reason is not None and isinstance(reason, (TimeoutError, socket.timeout, ConnectionError, OSError)):
            return True
        message = str(exc).lower()
        return any(term in message for term in (
            "timed out", "timeout", "connection reset", "connection aborted",
            "remote end closed", "incomplete read", "temporarily unavailable",
            "unexpected eof", "broken pipe", "network is unreachable",
        )) or isinstance(exc, (TimeoutError, socket.timeout, ConnectionError,
                               ConnectionResetError, BrokenPipeError,
                               http.client.IncompleteRead, http.client.RemoteDisconnected))
    # google-genai/httpx exceptions vary by SDK version; use narrow class/message
    # matching and explicitly exclude authentication, permission and quota errors.
    low = str(exc).lower()
    if any(term in low for term in ("429", "quota", "resource_exhausted", "unauthorized", "401", "403", "permission denied")):
        return False
    return any(term in low for term in (
        "readtimeout", "connecttimeout", "timed out", "timeout", "connection reset",
        "connection aborted", "remoteprotocolerror", "server disconnected",
        "incomplete read", "unexpected eof", "temporarily unavailable",
    ))

"""Versioned conversation import/export with strict structural validation."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from typing import Any, Iterable

SCHEMA_VERSION = 1
MAX_MESSAGES = 10_000
MAX_TEXT_CHARS = 2_000_000
_ALLOWED_ROLES = {"system", "user", "assistant", "tool"}

class ConversationFormatError(ValueError):
    pass

def _clean_message(message: dict[str, Any], index: int) -> dict[str, str]:
    if not isinstance(message, dict):
        raise ConversationFormatError(f"Message {index} must be an object")
    role = str(message.get("role", "")).strip().lower()
    if role not in _ALLOWED_ROLES:
        raise ConversationFormatError(f"Message {index} has an unsupported role")
    content = message.get("content", "")
    if not isinstance(content, str):
        raise ConversationFormatError(f"Message {index} content must be text")
    if len(content) > MAX_TEXT_CHARS:
        raise ConversationFormatError(f"Message {index} is too large")
    result = {"role": role, "content": content}
    for key in ("name", "mode", "created_at"):
        value = message.get(key)
        if value is not None and isinstance(value, (str, int, float, bool)):
            result[key] = str(value)[:300]
    return result

def export_conversation(messages: Iterable[dict[str, Any]], title: str = "New Chat",
                        conversation_id: str | None = None) -> str:
    normalized = []
    total = 0
    for index, message in enumerate(messages):
        if index >= MAX_MESSAGES:
            raise ConversationFormatError(f"Conversation exceeds {MAX_MESSAGES} messages")
        clean = _clean_message(message, index)
        total += len(clean["content"])
        if total > MAX_TEXT_CHARS:
            raise ConversationFormatError("Conversation exceeds total text limit")
        normalized.append(clean)
    payload = {"format": "indo-ai-conversation", "schema_version": SCHEMA_VERSION,
               "conversation_id": str(conversation_id or "")[:200], "title": str(title)[:300],
               "exported_at": datetime.now(timezone.utc).isoformat(), "messages": normalized}
    return json.dumps(payload, ensure_ascii=False, indent=2)

def import_conversation(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        if len(raw) > 20 * 1024 * 1024:
            raise ConversationFormatError("Import file exceeds 20 MB")
        try:
            raw = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ConversationFormatError("Import file must be UTF-8 text") from exc
    if not isinstance(raw, str) or len(raw) > 20 * 1024 * 1024:
        raise ConversationFormatError("Import content is invalid or too large")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConversationFormatError("Import file is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("format") != "indo-ai-conversation":
        raise ConversationFormatError("This is not an Indo AI conversation export")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ConversationFormatError("Unsupported conversation schema version")
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
        raise ConversationFormatError("Messages must be a valid list within the size limit")
    normalized = []
    total = 0
    for index, message in enumerate(messages):
        clean = _clean_message(message, index)
        total += len(clean["content"])
        if total > MAX_TEXT_CHARS:
            raise ConversationFormatError("Conversation exceeds total text limit")
        normalized.append(clean)
    return {"format": payload["format"], "schema_version": SCHEMA_VERSION,
            "conversation_id": str(payload.get("conversation_id", ""))[:200],
            "title": str(payload.get("title", "New Chat"))[:300], "messages": normalized}

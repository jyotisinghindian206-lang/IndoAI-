"""Typed, defensive configuration helpers for Indo AI.

Secrets are never included in repr(), public summaries, or validation messages.
Existing application configuration remains authoritative until integration is tested.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
import os
from pathlib import Path
from typing import Mapping, Any

_TRUE = {"1", "true", "yes", "on", "enabled"}
_FALSE = {"0", "false", "no", "off", "disabled"}


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def _int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError, OverflowError):
        return default
    return max(low, min(high, parsed))


def _text(value: Any, default: str, limit: int = 200) -> str:
    if value is None:
        return default
    result = " ".join(str(value).split())
    return result[:limit] or default


@dataclass(frozen=True, repr=False)
class IndoSettings:
    app_name: str = "Indo AI - Mira"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    request_timeout_seconds: int = 45
    max_upload_mb: int = 20
    max_message_chars: int = 20_000
    max_history_messages: int = 80
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    diagnostics_enabled: bool = True
    public_registration_enabled: bool = True
    debug_errors: bool = False
    database_path: str = "indo_ai.sqlite3"

    def __repr__(self) -> str:
        # This settings model intentionally has no secret fields.
        values = ", ".join(f"{f.name}={getattr(self, f.name)!r}" for f in fields(self))
        return f"IndoSettings({values})"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    def public_dict(self) -> dict[str, Any]:
        """Return safe settings suitable for a diagnostics response."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "port": self.port,
            "request_timeout_seconds": self.request_timeout_seconds,
            "max_upload_mb": self.max_upload_mb,
            "max_message_chars": self.max_message_chars,
            "max_history_messages": self.max_history_messages,
            "rate_limit_requests": self.rate_limit_requests,
            "rate_limit_window_seconds": self.rate_limit_window_seconds,
            "diagnostics_enabled": self.diagnostics_enabled,
            "public_registration_enabled": self.public_registration_enabled,
            "debug_errors": self.debug_errors,
            # Database paths can reveal local layout; expose only whether configured.
            "database_configured": bool(self.database_path),
        }


def load_settings(source: Mapping[str, Any] | None = None) -> IndoSettings:
    """Build validated settings from a mapping, defaulting to process environment."""
    env = os.environ if source is None else source
    return IndoSettings(
        app_name=_text(env.get("INDO_APP_NAME"), "Indo AI - Mira", 100),
        environment=_text(env.get("INDO_ENVIRONMENT", env.get("ENVIRONMENT")), "development", 30).lower(),
        host=_text(env.get("INDO_HOST"), "127.0.0.1", 255),
        port=_int(env.get("INDO_PORT"), 8000, 1, 65535),
        request_timeout_seconds=_int(env.get("INDO_REQUEST_TIMEOUT"), 45, 3, 300),
        max_upload_mb=_int(env.get("INDO_MAX_UPLOAD_MB"), 20, 1, 250),
        max_message_chars=_int(env.get("INDO_MAX_MESSAGE_CHARS"), 20_000, 100, 1_000_000),
        max_history_messages=_int(env.get("INDO_MAX_HISTORY_MESSAGES"), 80, 1, 2_000),
        rate_limit_requests=_int(env.get("INDO_RATE_LIMIT_REQUESTS"), 60, 1, 100_000),
        rate_limit_window_seconds=_int(env.get("INDO_RATE_LIMIT_WINDOW_SECONDS"), 60, 1, 86_400),
        diagnostics_enabled=_bool(env.get("INDO_DIAGNOSTICS_ENABLED"), True),
        public_registration_enabled=_bool(env.get("INDO_PUBLIC_REGISTRATION_ENABLED"), True),
        debug_errors=_bool(env.get("INDO_DEBUG_ERRORS"), False),
        database_path=_text(env.get("INDO_DATABASE_PATH"), "indo_ai.sqlite3", 500),
    )


def validate_settings(settings: IndoSettings) -> list[str]:
    """Return actionable warnings without printing secrets or mutating settings."""
    warnings: list[str] = []
    if settings.is_production and settings.debug_errors:
        warnings.append("Debug error details should be disabled in production.")
    if settings.is_production and settings.host in {"127.0.0.1", "localhost"}:
        warnings.append("Production host is loopback-only; confirm this is intentional for your deployment.")
    if settings.max_message_chars > 100_000:
        warnings.append("The message limit is unusually high and may increase memory use.")
    if settings.max_upload_mb > 100:
        warnings.append("Large upload limits can increase memory and processing pressure.")
    if settings.rate_limit_requests > 5_000:
        warnings.append("The rate limit is very permissive; review abuse and provider-cost risks.")
    if not settings.diagnostics_enabled:
        warnings.append("Diagnostics are disabled by configuration.")
    return warnings


def load_dotenv_safe(path: str | Path, environ: dict[str, str] | None = None) -> list[str]:
    """Load simple KEY=VALUE entries without overwriting existing environment values.

    Returns names of accepted keys only. Does not return or log values.
    This is optional; the legacy app already has its own environment loader.
    """
    target = os.environ if environ is None else environ
    accepted: list[str] = []
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return accepted
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in target and value:
            target[key] = value
            accepted.append(key)
    return accepted

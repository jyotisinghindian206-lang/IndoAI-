"""Thread-safe feature flags with safe defaults and environment overrides."""
from __future__ import annotations
from dataclasses import dataclass
import os
import threading
from typing import Mapping

_TRUE = {"1", "true", "yes", "on", "enabled"}

@dataclass(frozen=True)
class FeatureFlag:
    name: str
    default: bool
    description: str
    environment_key: str | None = None

class FeatureFlagRegistry:
    """Small registry that never enables an unknown flag implicitly."""
    def __init__(self, flags: list[FeatureFlag] | None = None, env: Mapping[str, str] | None = None):
        self._lock = threading.RLock()
        self._env = os.environ if env is None else env
        defaults = flags or [
            FeatureFlag("diagnostics", True, "Expose non-sensitive diagnostics."),
            FeatureFlag("conversation_export", True, "Allow users to export their own chats."),
            FeatureFlag("experimental_ui", False, "Enable experimental UI components."),
            FeatureFlag("provider_fallback", True, "Allow configured provider fallback."),
            FeatureFlag("anonymous_analytics", False, "Collect anonymous product analytics."),
        ]
        self._flags = {flag.name: flag for flag in defaults}
        self._overrides: dict[str, bool] = {}

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._flags))

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            if name in self._overrides:
                return self._overrides[name]
            env_key = flag.environment_key or f"INDO_FEATURE_{name.upper()}"
            env_value = self._env.get(env_key)
            if env_value is not None:
                return str(env_value).strip().lower() in _TRUE
            return flag.default

    def set_override(self, name: str, enabled: bool | None) -> bool:
        """Set a process-local override; None removes it. False means unknown flag."""
        with self._lock:
            if name not in self._flags:
                return False
            if enabled is None:
                self._overrides.pop(name, None)
            else:
                self._overrides[name] = bool(enabled)
            return True

    def public_snapshot(self) -> dict[str, bool]:
        with self._lock:
            return {name: self.is_enabled(name) for name in sorted(self._flags)}

    def describe(self) -> list[dict[str, object]]:
        with self._lock:
            return [{"name": flag.name, "enabled": self.is_enabled(flag.name),
                     "description": flag.description} for flag in self._flags.values()]

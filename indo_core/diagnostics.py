"""Non-invasive application diagnostics; never returns credential values."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import importlib.util
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Callable

@dataclass(frozen=True)
class DiagnosticItem:
    name: str
    status: str
    detail: str

@dataclass(frozen=True)
class DiagnosticReport:
    generated_at_epoch: float
    python_version: str
    platform_name: str
    checks: tuple[DiagnosticItem, ...]

    @property
    def healthy(self) -> bool:
        return all(item.status not in {"error", "critical"} for item in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {"healthy": self.healthy, "generated_at_epoch": self.generated_at_epoch,
                "python_version": self.python_version, "platform": self.platform_name,
                "checks": [asdict(item) for item in self.checks]}


def run_diagnostics(base_dir: str | Path | None = None,
                    required_modules: tuple[str, ...] = ("fastapi", "uvicorn", "pydantic"),
                    disk_warning_mb: int = 250,
                    custom_checks: dict[str, Callable[[], tuple[str, str]]] | None = None) -> DiagnosticReport:
    root = Path(base_dir or Path.cwd()).resolve()
    checks: list[DiagnosticItem] = []
    for module in required_modules:
        found = importlib.util.find_spec(module) is not None
        checks.append(DiagnosticItem(f"dependency:{module}", "ok" if found else "warning",
                                     "Available" if found else "Not installed in this Python environment"))
    try:
        usage = shutil.disk_usage(root if root.exists() else Path.cwd())
        free_mb = usage.free // (1024 * 1024)
        status = "warning" if free_mb < disk_warning_mb else "ok"
        checks.append(DiagnosticItem("disk_space", status, f"Approximately {free_mb} MB free"))
    except OSError:
        checks.append(DiagnosticItem("disk_space", "warning", "Disk usage could not be read"))
    for name, env_key in (("gemini_provider", "GEMINI_API_KEY"),
                          ("sarvam_provider", "SARVAM_API_KEY"),
                          ("elevenlabs_provider", "ELEVENLABS_API_KEY")):
        configured = bool(os.getenv(env_key, "").strip())
        checks.append(DiagnosticItem(name, "configured" if configured else "not_configured",
                                     "Credential is configured" if configured else "Optional provider is not configured"))
    checks.append(DiagnosticItem("working_directory", "ok" if root.exists() else "warning",
                                 "Project directory exists" if root.exists() else "Project directory does not exist"))
    for name, check in (custom_checks or {}).items():
        try:
            status, detail = check()
            checks.append(DiagnosticItem(f"custom:{name}", str(status)[:30], str(detail)[:300]))
        except Exception as exc:
            checks.append(DiagnosticItem(f"custom:{name}", "warning", f"Check failed: {type(exc).__name__}"))
    return DiagnosticReport(time.time(), sys.version.split()[0], platform.platform(), tuple(checks))

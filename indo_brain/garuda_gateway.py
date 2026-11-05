"""GARUDA tool gateway with default-deny registration and one-time approvals.

This module does not expose shell or filesystem execution by itself. Callers must
register narrowly scoped handlers that enforce their own path/account sandbox.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Mapping
from .garuda_security import TOOL_POLICIES, authorize_tool_action

class ApprovalStore:
    def __init__(self, db_path: str | os.PathLike[str], secret: str | None = None):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = (secret or os.getenv("INDO_SESSION_SECRET") or secrets.token_hex(32)).encode()
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS tool_approvals (token_hash TEXT PRIMARY KEY, account_hash TEXT NOT NULL, action TEXT NOT NULL, expires_at REAL NOT NULL, consumed_at REAL)")
            db.commit()
        try: os.chmod(self.path, 0o600)
        except OSError: pass

    def _hash(self, value: str) -> str:
        return hmac.new(self.secret, str(value).encode(), hashlib.sha256).hexdigest()

    def issue(self, account_id: str, action: str, *, explicitly_confirmed: bool, ttl_seconds: int = 120) -> str:
        name = str(action or "").strip().lower()
        policy = TOOL_POLICIES.get(name)
        if not account_id or not policy:
            raise PermissionError("Unknown action or account.")
        if not policy.get("approval"):
            raise ValueError("This action does not require an approval token.")
        if explicitly_confirmed is not True:
            raise PermissionError("Explicit user confirmation is required.")
        token = secrets.token_urlsafe(32)
        now = time.time()
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.execute("DELETE FROM tool_approvals WHERE expires_at < ? OR consumed_at IS NOT NULL", (now,))
            db.execute("INSERT INTO tool_approvals(token_hash,account_hash,action,expires_at) VALUES(?,?,?,?)",
                       (self._hash(token), self._hash(account_id), name, now + max(30, min(int(ttl_seconds), 300))))
            db.commit()
        return token

    def consume(self, token: str, account_id: str, action: str) -> bool:
        if not token or not account_id: return False
        now = time.time()
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute("UPDATE tool_approvals SET consumed_at=? WHERE token_hash=? AND account_hash=? AND action=? AND expires_at>=? AND consumed_at IS NULL",
                             (now, self._hash(token), self._hash(account_id), str(action).lower(), now))
            ok = cur.rowcount == 1
            db.commit()
            return ok

class ToolGateway:
    """Execute only explicitly registered handlers after policy and approval checks."""
    def __init__(self, handlers: Mapping[str, Callable[..., Any]], approval_store: ApprovalStore,
                 allowed_tools: set[str] | None = None):
        self.handlers = {str(k).lower(): v for k, v in handlers.items() if callable(v)}
        self.approvals = approval_store
        self.allowed_tools = set(allowed_tools) if allowed_tools is not None else set(self.handlers)

    def execute(self, tool_name: str, account_id: str, *, args: dict[str, Any] | None = None,
                approval_token: str | None = None) -> Any:
        name = str(tool_name or "").strip().lower()
        if name not in self.handlers or name not in self.allowed_tools:
            raise PermissionError("Tool is not registered and allowlisted.")
        policy = TOOL_POLICIES.get(name)
        if not policy:
            raise PermissionError("Tool has no GARUDA policy.")
        if policy.get("approval") and not self.approvals.consume(approval_token or "", account_id, name):
            raise PermissionError("A valid, unused, account-bound approval is required.")
        decision = authorize_tool_action(name, user_approved=bool(policy.get("approval")), allowed_tools=self.allowed_tools)
        if not decision.get("allowed"):
            raise PermissionError(decision.get("reason", "GARUDA denied the action."))
        # The registered handler remains responsible for sandboxing, ownership checks and bounded I/O.
        return self.handlers[name](**(args or {}))

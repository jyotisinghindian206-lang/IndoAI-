"""Account-scoped, approval-gated multi-step workflows for Indo AI.

This orchestrator plans and tracks work. It never executes arbitrary code, shell
commands, purchases, messages, deployments, or other external side effects.
Such actions require a separately implemented, explicitly authorized connector.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3, time, uuid
from pathlib import Path
from typing import Any

_SECRET = re.compile(r"\b(password|api[_ -]?key|secret|token|otp|private[_ -]?key)\b", re.I)

def _account_hash(identity: str) -> str:
    return hashlib.sha256(str(identity).strip().casefold().encode("utf-8")).hexdigest()

def _clean(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]

def _steps_for(goal: str) -> list[dict[str, Any]]:
    low = goal.casefold()
    if re.search(r"\b(code|app|software|api|debug|integrat|feature|deploy)\w*\b", low):
        labels = ["Inspect current source and constraints", "Design the smallest compatible change", "Implement in an isolated working copy", "Run focused tests and inspect regressions", "Present the diff and request approval for production changes"]
    elif re.search(r"\b(research|compare|investigat|report|latest)\w*\b", low):
        labels = ["Clarify the research question and scope", "Gather relevant sources with dates", "Cross-check important claims", "Synthesize findings and uncertainty", "Present the report with source links"]
    else:
        labels = ["Define the outcome and constraints", "Gather relevant context", "Break the work into ordered actions", "Complete and verify permitted actions", "Report results and remaining decisions"]
    return [{"id": f"step_{i+1}", "title": title, "status": "pending", "requires_approval": i == 2 and bool(re.search(r"\b(deploy|publish|send|delete|purchase|pay|commit|production)\b", goal, re.I)), "result": ""} for i, title in enumerate(labels)]

class AutonomousExecution:
    def __init__(self, data_dir: str | Path):
        root = Path(data_dir); root.mkdir(parents=True, exist_ok=True)
        self.path = root / "indo_autonomous_workflows.sqlite3"
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY, account TEXT NOT NULL, goal TEXT NOT NULL, status TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0, steps_json TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_workflows_account ON workflows(account,updated_at DESC)")
            db.commit()
    def _db(self):
        db=sqlite3.connect(str(self.path),timeout=8); db.row_factory=sqlite3.Row; db.execute("PRAGMA busy_timeout=8000"); return db
    def create(self, identity: str, goal: str) -> dict[str, Any]:
        goal=_clean(goal,4000)
        if not identity: raise ValueError("Sign-in required")
        if len(goal)<5: raise ValueError("Please provide a more specific goal")
        if _SECRET.search(goal): raise ValueError("Do not include passwords, API keys, tokens or other secrets in workflow goals")
        now=int(time.time()); wid=uuid.uuid4().hex
        steps=_steps_for(goal)
        with self._db() as db:
            db.execute("INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?)",(wid,_account_hash(identity),goal,"awaiting_approval",0,json.dumps(steps),now,now)); db.commit()
        return self.get(identity,wid)
    def get(self, identity: str, workflow_id: str) -> dict[str, Any] | None:
        with self._db() as db: row=db.execute("SELECT * FROM workflows WHERE id=? AND account=?",(workflow_id,_account_hash(identity))).fetchone()
        return self._public(row) if row else None
    def list(self, identity: str, limit: int=20) -> list[dict[str, Any]]:
        with self._db() as db: rows=db.execute("SELECT * FROM workflows WHERE account=? ORDER BY updated_at DESC LIMIT ?",(_account_hash(identity),max(1,min(int(limit),50)))).fetchall()
        return [self._public(r) for r in rows]
    def approve(self, identity: str, workflow_id: str) -> dict[str, Any] | None:
        with self._db() as db:
            row=db.execute("SELECT * FROM workflows WHERE id=? AND account=?",(workflow_id,_account_hash(identity))).fetchone()
            if not row:return None
            if row["status"]!="awaiting_approval": return self._public(row)
            now=int(time.time()); db.execute("UPDATE workflows SET approved=1,status='ready',updated_at=? WHERE id=? AND account=?",(now,workflow_id,_account_hash(identity))); db.commit()
        return self.get(identity,workflow_id)
    def cancel(self, identity: str, workflow_id: str) -> dict[str, Any] | None:
        """Cancel an unfinished workflow owned by this account."""
        if not identity:
            return None
        with self._db() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=? AND account=?", (workflow_id, _account_hash(identity))).fetchone()
            if not row:
                return None
            if row["status"] == "completed":
                raise ValueError("Completed workflows cannot be cancelled")
            now = int(time.time())
            db.execute("UPDATE workflows SET status='cancelled',updated_at=? WHERE id=? AND account=?", (now, workflow_id, _account_hash(identity)))
            db.commit()
        return self.get(identity, workflow_id)

    def delete(self, identity: str, workflow_id: str) -> bool:
        """Delete a workflow only from the authenticated owner's records."""
        if not identity:
            return False
        with self._db() as db:
            cur = db.execute("DELETE FROM workflows WHERE id=? AND account=?", (workflow_id, _account_hash(identity)))
            db.commit()
            return cur.rowcount > 0

    def export_account(self, identity: str) -> list[dict[str, Any]]:
        """Return an account-scoped snapshot for encryption by the application layer."""
        if not identity:
            return []
        account = _account_hash(identity)
        with self._db() as db:
            rows = db.execute("SELECT * FROM workflows WHERE account=? ORDER BY updated_at DESC LIMIT 500", (account,)).fetchall()
        return {"account": account, "records": [dict(r) for r in rows]}

    def import_account(self, identity: str, snapshot: dict[str, Any]) -> int:
        """Merge a decrypted, identity-bound snapshot without overwriting newer rows."""
        if not identity:
            raise ValueError("Sign-in required")
        account = _account_hash(identity)
        if not isinstance(snapshot, dict) or snapshot.get("account") != account:
            raise ValueError("Workflow snapshot belongs to a different account")
        records = snapshot.get("records")
        if not isinstance(records, list) or len(records) > 500:
            raise ValueError("Invalid workflow snapshot")
        imported = 0
        with self._db() as db:
            for item in records:
                if not isinstance(item, dict):
                    continue
                wid = str(item.get("id") or "")
                goal = _clean(item.get("goal"), 4000)
                status = str(item.get("status") or "")
                steps = item.get("steps_json")
                if not re.fullmatch(r"[a-f0-9]{32}", wid) or not goal or status not in {"awaiting_approval", "ready", "in_progress", "blocked", "completed", "cancelled"}:
                    continue
                try:
                    parsed = json.loads(steps) if isinstance(steps, str) else steps
                    if not isinstance(parsed, list) or len(parsed) > 30:
                        continue
                    steps_json = json.dumps(parsed, ensure_ascii=False)
                    created = max(0, int(item.get("created_at", 0)))
                    updated = max(created, int(item.get("updated_at", created)))
                    approved = 1 if item.get("approved") in (1, True, "1") else 0
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                existing = db.execute("SELECT updated_at FROM workflows WHERE id=? AND account=?", (wid, account)).fetchone()
                if existing and int(existing["updated_at"]) >= updated:
                    continue
                db.execute("INSERT INTO workflows(id,account,goal,status,approved,steps_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET goal=excluded.goal,status=excluded.status,approved=excluded.approved,steps_json=excluded.steps_json,created_at=excluded.created_at,updated_at=excluded.updated_at WHERE workflows.account=excluded.account", (wid, account, goal, status, approved, steps_json, created, updated))
                imported += 1
            db.commit()
        return imported

    def advance(self, identity: str, workflow_id: str, step_id: str, status: str, result: str="") -> dict[str, Any] | None:
        if status not in {"in_progress","completed","blocked","skipped"}: raise ValueError("Unsupported step status")
        with self._db() as db:
            row=db.execute("SELECT * FROM workflows WHERE id=? AND account=?",(workflow_id,_account_hash(identity))).fetchone()
            if not row:return None
            if not row["approved"]: raise PermissionError("Approve this workflow before advancing steps")
            steps=json.loads(row["steps_json"])
            idx=next((i for i,s in enumerate(steps) if s["id"]==step_id),None)
            if idx is None: raise ValueError("Unknown workflow step")
            if steps[idx]["requires_approval"]: raise PermissionError("This consequential step needs separate explicit approval; it is not executable through this tracker")
            if status=="in_progress" and any(s["status"] not in {"completed","skipped"} for s in steps[:idx]): raise ValueError("Complete or skip earlier steps first")
            steps[idx]["status"]=status; steps[idx]["result"]=_clean(result,1000)
            overall="completed" if all(s["status"] in {"completed","skipped"} for s in steps) else ("blocked" if status=="blocked" else "in_progress")
            now=int(time.time()); db.execute("UPDATE workflows SET steps_json=?,status=?,updated_at=? WHERE id=? AND account=?",(json.dumps(steps),overall,now,workflow_id,_account_hash(identity))); db.commit()
        return self.get(identity,workflow_id)
    @staticmethod
    def _public(row):
        return {"id":row["id"],"goal":row["goal"],"status":row["status"],"approved":bool(row["approved"]),"steps":json.loads(row["steps_json"]),"created_at":row["created_at"],"updated_at":row["updated_at"],"execution_policy":"approval-gated tracker; no arbitrary code or external side effects"}

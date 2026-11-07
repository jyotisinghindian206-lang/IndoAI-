"""Account-scoped cross-session project threads for Indo AI.

Stores explicit project decisions/milestones and completed-turn checkpoints. User text
is treated as untrusted data; no cross-account sharing and no autonomous actions occur.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3, time, uuid
from pathlib import Path

_PROJECT = re.compile(r"\b(?:project|app|repo|codebase)\s+(?:called|named)?\s+([a-z0-9][a-z0-9 _.-]{1,48})", re.I)
_DECISION = re.compile(r"\b(?:i choose|we choose|decision:|decided to|let's use|lets use|we will use|use this approach|final choice)\b", re.I)
_MILESTONE = re.compile(r"\b(?:completed|finished|implemented|deployed|milestone|step\s*\d+|phase\s*\d+|now works|fixed)\b", re.I)
_SKIP = re.compile(r"\b(?:password|passphrase|api[_ -]?key|secret(?:[_ -]?key)?|access[_ -]?token|refresh[_ -]?token|bearer|otp|private[_ -]?key|recovery[_ -]?code)\b", re.I)

def _clean(s, n=1200): return re.sub(r"\s+", " ", str(s or "")).strip()[:n]
def _hash(identity): return hashlib.sha256(str(identity).strip().casefold().encode()).hexdigest()
def _project_name(message, hint=""):
    hint = _clean(hint, 80).casefold()
    if hint: return hint
    if re.search(r"\bindo\s*ai\b", message, re.I): return "indo ai"
    m = _PROJECT.search(message)
    return _clean(m.group(1), 60).strip(" .,-").casefold() if m else ""

class CrossSessionProjectThreads:
    def __init__(self, data_dir):
        root = Path(data_dir); root.mkdir(parents=True, exist_ok=True)
        self.path = root / "indo_project_threads.sqlite3"
        with self._db() as c:
            c.execute("CREATE TABLE IF NOT EXISTS project_threads(user_hash TEXT, project_key TEXT, project_name TEXT, created_at INTEGER, updated_at INTEGER, PRIMARY KEY(user_hash,project_key))")
            c.execute("CREATE TABLE IF NOT EXISTS project_events(id TEXT PRIMARY KEY,user_hash TEXT,project_key TEXT,event_type TEXT,content TEXT,session_id TEXT,created_at INTEGER,source TEXT, UNIQUE(user_hash,project_key,event_type,content))")
            c.execute("CREATE INDEX IF NOT EXISTS idx_project_events ON project_events(user_hash,project_key,created_at DESC)")
            c.commit()
    def _db(self):
        c=sqlite3.connect(str(self.path),timeout=5); c.row_factory=sqlite3.Row; c.execute("PRAGMA busy_timeout=5000"); return c
    def record_turn(self, identity, message, assistant_text="", *, session_id="", project_hint=""):
        if not identity: return {"saved":False,"reason":"missing_identity"}
        msg=_clean(message); answer=_clean(assistant_text,1000)
        if len(msg)<12 or _SKIP.search(msg): return {"saved":False,"reason":"not_project_content"}
        name=_project_name(msg,project_hint)
        if not name: return {"saved":False,"reason":"project_not_identified"}
        # Persist only explicit decisions/milestones, plus a compact checkpoint when relevant.
        events=[]
        if _DECISION.search(msg): events.append(("decision",msg))
        if _MILESTONE.search(msg): events.append(("milestone",msg))
        if not events and re.search(r"\b(implement|build|integrate|architecture|database|deployment|feature|bug|fix)\b",msg,re.I):
            events.append(("project_note",msg))
        if answer and events: events.append(("checkpoint",answer))
        if not events: return {"saved":False,"reason":"no_project_event"}
        uh=_hash(identity); key=re.sub(r"[^a-z0-9]+","_",name).strip("_")[:70]; now=int(time.time())
        with self._db() as c:
            c.execute("INSERT INTO project_threads VALUES(?,?,?,?,?) ON CONFLICT(user_hash,project_key) DO UPDATE SET project_name=excluded.project_name,updated_at=excluded.updated_at",(uh,key,name,now,now))
            saved=0
            for typ,content in events:
                cur=c.execute("INSERT OR IGNORE INTO project_events(id,user_hash,project_key,event_type,content,session_id,created_at,source) VALUES(?,?,?,?,?,?,?,?)",(uuid.uuid4().hex,uh,key,typ,content[:1200],_clean(session_id,120),now,"completed_chat" if typ=="checkpoint" else "explicit_user_message"))
                saved += max(0,cur.rowcount)
            # Bound history per project to avoid unbounded growth.
            c.execute("DELETE FROM project_events WHERE user_hash=? AND project_key=? AND id NOT IN (SELECT id FROM project_events WHERE user_hash=? AND project_key=? ORDER BY created_at DESC LIMIT 250)",(uh,key,uh,key))
            c.commit()
        return {"saved":bool(saved),"project":name,"events_saved":saved}
    def list_projects(self, identity, limit=30):
        if not identity:return []
        with self._db() as c:
            rows=c.execute("SELECT t.project_name,t.updated_at,COUNT(e.id) event_count FROM project_threads t LEFT JOIN project_events e ON e.user_hash=t.user_hash AND e.project_key=t.project_key WHERE t.user_hash=? GROUP BY t.user_hash,t.project_key ORDER BY t.updated_at DESC LIMIT ?",(_hash(identity),max(1,min(int(limit),100)))).fetchall()
        return [dict(r) for r in rows]
    def context(self, identity, project, limit=12):
        if not identity or not project:return ""
        key=re.sub(r"[^a-z0-9]+","_",_clean(project,80).casefold()).strip("_")[:70]
        with self._db() as c:
            rows=c.execute("SELECT event_type,content,created_at FROM project_events WHERE user_hash=? AND project_key=? ORDER BY created_at DESC LIMIT ?",(_hash(identity),key,max(1,min(int(limit),30)))).fetchall()
        if not rows:return ""
        lines=[f"CROSS-SESSION PROJECT THREAD: {project[:80]}"]
        for r in reversed(rows):
            stamp=time.strftime("%Y-%m-%d",time.gmtime(r["created_at"]))
            lines.append(f"- [{r['event_type']} | {stamp}] {r['content'][:500]}")
        return "\n".join(lines)[:5000]
    def events(self, identity, project, limit=50):
        if not identity:return []
        key=re.sub(r"[^a-z0-9]+","_",_clean(project,80).casefold()).strip("_")[:70]
        with self._db() as c:
            rows=c.execute("SELECT id,event_type,content,session_id,created_at,source FROM project_events WHERE user_hash=? AND project_key=? ORDER BY created_at DESC LIMIT ?",(_hash(identity),key,max(1,min(int(limit),100)))).fetchall()
        return [dict(r) for r in rows]

    def delete_project(self, identity, project):
        """Delete one account-owned project thread and all its events."""
        if not identity or not project:
            return 0
        key = re.sub(r"[^a-z0-9]+", "_", _clean(project, 80).casefold()).strip("_")[:70]
        uh = _hash(identity)
        with self._db() as c:
            cur = c.execute("DELETE FROM project_events WHERE user_hash=? AND project_key=?", (uh, key))
            removed = max(0, cur.rowcount)
            c.execute("DELETE FROM project_threads WHERE user_hash=? AND project_key=?", (uh, key))
            c.commit()
        return removed

    def delete_event(self, identity, event_id):
        """Delete a single event only when it belongs to the requesting account."""
        if not identity or not event_id:
            return False
        with self._db() as c:
            cur = c.execute("DELETE FROM project_events WHERE user_hash=? AND id=?", (_hash(identity), str(event_id)[:80]))
            c.commit()
            return cur.rowcount > 0

    def cloud_export(self, identity, cipher):
        """Return an encrypted, account-only snapshot suitable for Supabase JSON storage."""
        if not identity: return ""
        uh=_hash(identity)
        with self._db() as c:
            projects=[dict(r) for r in c.execute("SELECT project_key,project_name,created_at,updated_at FROM project_threads WHERE user_hash=?",(uh,)).fetchall()]
            events=[dict(r) for r in c.execute("SELECT id,project_key,event_type,content,session_id,created_at,source FROM project_events WHERE user_hash=? ORDER BY created_at DESC LIMIT 2000",(uh,)).fetchall()]
        payload=json.dumps({"version":1,"projects":projects,"events":events},ensure_ascii=False,separators=(",",":" )).encode()
        return cipher.encrypt(payload).decode("ascii")

    def cloud_import(self, identity, encrypted_snapshot, cipher):
        """Merge a trusted encrypted snapshot without deleting newer local events."""
        if not identity or not encrypted_snapshot: return 0
        try: payload=json.loads(cipher.decrypt(str(encrypted_snapshot).encode("ascii")).decode("utf-8"))
        except Exception: return 0
        if payload.get("version") != 1: return 0
        uh=_hash(identity); count=0
        with self._db() as c:
            for p in payload.get("projects",[])[:200]:
                c.execute("INSERT INTO project_threads VALUES(?,?,?,?,?) ON CONFLICT(user_hash,project_key) DO UPDATE SET updated_at=MAX(project_threads.updated_at,excluded.updated_at)",(uh,p["project_key"],p["project_name"],p["created_at"],p["updated_at"]))
            for e in payload.get("events",[])[:2000]:
                cur=c.execute("INSERT OR IGNORE INTO project_events(id,user_hash,project_key,event_type,content,session_id,created_at,source) VALUES(?,?,?,?,?,?,?,?)",(e["id"],uh,e["project_key"],e["event_type"],e["content"],e.get("session_id",""),e["created_at"],e.get("source","cloud_restore")))
                count += max(0,cur.rowcount)
            c.commit()
        return count


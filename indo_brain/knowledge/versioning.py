"""Consent-gated versioned knowledge records with account-scope isolation."""
from __future__ import annotations
import hashlib, json, os, sqlite3, time, uuid
from pathlib import Path
from contextlib import contextmanager

class VersionedKnowledgeStore:
    def __init__(self, db_path=None):
        if db_path is None:
            root = Path(os.getenv("INDO_DATA_DIR", Path(__file__).resolve().parents[2] / "data")); root.mkdir(parents=True, exist_ok=True)
            db_path = root / "vishnu_knowledge.sqlite3"
        self.path = str(db_path); Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as c:
            c.execute("CREATE TABLE IF NOT EXISTS knowledge_versions (id TEXT PRIMARY KEY, scope_hash TEXT NOT NULL, topic TEXT NOT NULL, content TEXT NOT NULL, version INTEGER NOT NULL, created_at REAL NOT NULL, UNIQUE(scope_hash,topic,version))")
            c.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_scope_topic ON knowledge_versions(scope_hash,topic,version DESC)")
        try: os.chmod(self.path, 0o600)
        except OSError: pass
    @contextmanager
    def _db(self):
        c=sqlite3.connect(self.path,timeout=10)
        try:
            with c: yield c
        finally: c.close()
    @staticmethod
    def _scope(scope):
        s=str(scope or "").strip()
        if not s: raise ValueError("account scope is required")
        return hashlib.sha256(s.encode()).hexdigest()
    def add(self, scope, topic, content, *, consent=False):
        if consent is not True: raise PermissionError("explicit consent is required")
        topic=str(topic or "").strip()[:160]; content=str(content or "").strip()[:8000]
        if not topic or not content: raise ValueError("topic and content are required")
        sh=self._scope(scope)
        with self._db() as c:
            row=c.execute("SELECT COALESCE(MAX(version),0) FROM knowledge_versions WHERE scope_hash=? AND topic=?",(sh,topic)).fetchone()
            version=int(row[0])+1; rid=uuid.uuid4().hex
            c.execute("INSERT INTO knowledge_versions VALUES(?,?,?,?,?,?)",(rid,sh,topic,content,version,time.time()))
        return {"id":rid,"topic":topic,"version":version}
    def get(self, scope, topic):
        with self._db() as c:
            rows=c.execute("SELECT id,topic,content,version,created_at FROM knowledge_versions WHERE scope_hash=? AND topic=? ORDER BY version DESC LIMIT 20",(self._scope(scope),str(topic)[:160])).fetchall()
        return [{"id":r[0],"topic":r[1],"content":r[2],"version":r[3],"created_at":r[4]} for r in rows]
    def delete_topic(self, scope, topic):
        with self._db() as c:
            cur=c.execute("DELETE FROM knowledge_versions WHERE scope_hash=? AND topic=?",(self._scope(scope),str(topic)[:160])); return cur.rowcount

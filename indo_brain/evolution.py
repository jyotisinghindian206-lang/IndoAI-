"""Indo v14 evolution utilities: private persistent associations and safe project manifests.

The knowledge graph records co-mentioned terms only; it does not assert semantic truth.
Project inspection accepts caller-supplied text only and never opens arbitrary server paths.
"""
from __future__ import annotations
import ast, re, sqlite3, time
from collections import Counter
from pathlib import PurePosixPath
from typing import Any

_WORD = re.compile(r"[\w'-]+", re.UNICODE)
_STOP = {"the","and","for","with","that","this","from","into","your","you","are","was","were","will","would","could","should","have","has","had","what","when","where","which","while","about","please","make","build","create","add","improve","better","more","using","use","used","also","than","then"}
_SECRET_PARTS = {".env", "indo_secrets.env", "secrets.json", "credentials.json", "id_rsa", "id_ed25519"}
_MAX_TOTAL = 500_000

def _terms(text: str, limit: int = 40) -> list[str]:
    words = [w.casefold() for w in _WORD.findall(str(text or "")) if len(w) > 2 and w.casefold() not in _STOP]
    return [w for w, _ in Counter(words).most_common(limit)]

def _connect(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=8)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("CREATE TABLE IF NOT EXISTS nodes (term TEXT PRIMARY KEY, mentions INTEGER NOT NULL DEFAULT 0, first_seen REAL NOT NULL, last_seen REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS edges (source TEXT NOT NULL, target TEXT NOT NULL, weight INTEGER NOT NULL DEFAULT 0, last_seen REAL NOT NULL, PRIMARY KEY(source,target), FOREIGN KEY(source) REFERENCES nodes(term), FOREIGN KEY(target) REFERENCES nodes(term))")
    conn.commit()
    return conn

def remember_knowledge(db_path, text: str) -> dict[str, Any]:
    source = str(text or "").strip()
    if len(source) < 3 or len(source) > 12000:
        return {"saved": False, "error": "Text must be between 3 and 12,000 characters."}
    terms = _terms(source, 28)
    if not terms:
        return {"saved": False, "error": "No useful terms found."}
    now = time.time()
    conn = _connect(db_path)
    try:
        with conn:
            for term in terms:
                conn.execute("INSERT INTO nodes(term,mentions,first_seen,last_seen) VALUES(?,1,?,?) ON CONFLICT(term) DO UPDATE SET mentions=mentions+1,last_seen=excluded.last_seen", (term, now, now))
            # Connect terms that co-occurred in this submitted note; cap edges per note.
            pairs = [(terms[i], terms[j]) for i in range(len(terms)) for j in range(i+1, min(len(terms), i+7))]
            for a,b in pairs[:180]:
                left,right=sorted((a,b))
                conn.execute("INSERT INTO edges(source,target,weight,last_seen) VALUES(?,?,1,?) ON CONFLICT(source,target) DO UPDATE SET weight=weight+1,last_seen=excluded.last_seen", (left,right,now))
        return {"saved": True, "nodes_touched": len(terms), "associations_updated": min(180,len(pairs)), "storage": "per-user SQLite Library file", "meaning": "co-mentioned keyword associations only; not verified facts"}
    finally:
        conn.close()

def get_knowledge_graph(db_path, limit: int = 60) -> dict[str, Any]:
    limit=max(2,min(int(limit or 60),120))
    if not db_path.exists():
        return {"nodes": [], "edges": [], "count": 0, "persistence": "private per-user SQLite", "note": "No saved associations yet."}
    conn=_connect(db_path)
    try:
        nodes=[{"id":r[0],"label":r[0],"mentions":r[1],"last_seen":int(r[2])} for r in conn.execute("SELECT term,mentions,last_seen FROM nodes ORDER BY mentions DESC,last_seen DESC LIMIT ?",(limit,))]
        ids={n["id"] for n in nodes}
        edges=[{"source":a,"target":b,"weight":w} for a,b,w in conn.execute("SELECT source,target,weight FROM edges ORDER BY weight DESC,last_seen DESC LIMIT 240") if a in ids and b in ids]
        return {"nodes":nodes,"edges":edges,"count":len(nodes),"persistence":"private per-user SQLite","note":"Edges mean terms were co-mentioned in saved notes; they are not verified semantic or causal relationships."}
    finally: conn.close()

def analyze_project_manifest(files: list[dict[str,str]]) -> dict[str, Any]:
    if not files or len(files)>30:
        return {"error":"Supply between 1 and 30 text files."}
    total=0; safe=[]; skipped=[]; imports=Counter(); routes=[]; env_names=set(); syntax_errors=[]; tests=[]
    for item in files:
        raw=str(item.get("path", "" )).replace('\\','/')
        path=PurePosixPath(raw)
        name=path.name.casefold()
        if path.is_absolute() or '..' in path.parts or name in _SECRET_PARTS or any(part.startswith('.') and part not in {'.github'} for part in path.parts):
            skipped.append({"path":raw[:240],"reason":"unsafe, hidden or secret-like path"}); continue
        content=str(item.get("content", ""))
        total += len(content.encode('utf-8','ignore'))
        if total>_MAX_TOTAL:
            return {"error":"Combined project text exceeds 500 KB."}
        safe.append(raw[:240])
        suffix=path.suffix.lower()
        if suffix=='.py':
            try:
                tree=ast.parse(content,filename=raw)
                for node in ast.walk(tree):
                    if isinstance(node,ast.Import): imports.update(alias.name.split('.')[0] for alias in node.names)
                    elif isinstance(node,ast.ImportFrom) and node.module: imports.update([node.module.split('.')[0]])
                    elif isinstance(node,ast.Call):
                        f=node.func
                        if isinstance(f,ast.Attribute) and f.attr in {'get','post','put','delete','patch'} and isinstance(f.value,ast.Name) and f.value.id in {'app','router'} and node.args and isinstance(node.args[0],ast.Constant): routes.append({"method":f.attr.upper(),"path":str(node.args[0].value)[:180],"file":raw[:240]})
                        if isinstance(f,ast.Attribute) and f.attr=='getenv' and isinstance(f.value,ast.Name) and f.value.id=='os' and node.args and isinstance(node.args[0],ast.Constant): env_names.add(str(node.args[0].value))
                        if isinstance(f,ast.Name) and f.id=='environ' and node.args and isinstance(node.args[0],ast.Constant): env_names.add(str(node.args[0].value))
            except SyntaxError as exc: syntax_errors.append({"file":raw[:240],"line":exc.lineno,"message":exc.msg})
        if name.startswith('test_') or '/tests/' in ('/'+raw.lower()): tests.append(raw[:240])
    return {"files_inspected":len(safe),"files_skipped":skipped,"total_text_bytes":total,"python_imports":dict(imports.most_common(30)),"detected_fastapi_style_routes":routes[:100],"environment_variable_names":sorted(env_names)[:100],"test_files":tests[:60],"python_syntax_issues":syntax_errors,"limitations":["Manifest-only analysis: no arbitrary server paths were opened.","Dependency and route detection is heuristic.","Environment variable names are reported, never secret values.","No files were modified or executed."]}

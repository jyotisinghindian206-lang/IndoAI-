"""Indo AI Anticipatory Intelligence Engine (Levels 1-3).

Background-only public research, predictive preparation, and a lightweight topic
knowledge graph. It never waits on a research task in the chat streaming path.
Private account identity is hashed before persistence; research cache stores public
source metadata only. Verified summaries may be added to that account's encrypted DLM.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

_STOP = set("a an the and or but if then of to in on at for from with by is are was were be been being i me my mine we our us you your yours it this that these those can could would should will just very really do does did have has had am im ive dont doesnt not no yes please what how why when where which who is it about into over under".split())
_VOLATILE = re.compile(r"\b(today|tonight|now|currently|latest|recent|this week|price|weather|news|score|update|202[5-9])\b", re.I)
_SKIP = re.compile(r"^(hi+|hey+|hello|yo|sup|thanks|thank you|ok|okay|hmm+|bye|good night|gn|wsp)[!.? ]*$", re.I)


def _tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", str(value or "").casefold()) if x not in _STOP}


def _clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _topic_key(message: str) -> str:
    words = sorted(_tokens(message))
    return " ".join(words[:9])[:180]


class AnticipatoryIntelligenceEngine:
    """Bounded background research with cache, cancellation, prediction and graph."""

    def __init__(self, data_dir: str | Path, research_fn: Callable[[str], list[dict]], dlm=None,
                 cloud_sync: Callable[[str], Any] | None = None):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "indo_anticipatory.sqlite3"
        self.research_fn = research_fn
        self.dlm = dlm
        self.cloud_sync = cloud_sync
        self.enabled = os.getenv("INDO_ANTICIPATORY_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
        self.max_age = max(3600, int(os.getenv("INDO_RESEARCH_CACHE_TTL", "86400")))
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="indo-anticipatory")
        self.lock = threading.RLock()
        self.jobs: dict[str, dict[str, Any]] = {}
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(str(self.path), timeout=0.05)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=50")
        return con

    def _init_db(self):
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS research_cache (id TEXT PRIMARY KEY, user_hash TEXT NOT NULL, topic_key TEXT NOT NULL, query TEXT NOT NULL, title TEXT NOT NULL, snippet TEXT NOT NULL, url TEXT NOT NULL, domain TEXT NOT NULL, confidence REAL NOT NULL, researched_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, source_engine TEXT NOT NULL DEFAULT '')")
            con.execute("CREATE INDEX IF NOT EXISTS idx_anticipatory_user_topic ON research_cache(user_hash,topic_key,researched_at DESC)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_anticipatory_expiry ON research_cache(expires_at)")
            con.execute("CREATE TABLE IF NOT EXISTS topic_nodes (user_hash TEXT NOT NULL, node_key TEXT NOT NULL, label TEXT NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL, evidence_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_hash,node_key))")
            con.execute("CREATE TABLE IF NOT EXISTS topic_edges (user_hash TEXT NOT NULL, source_key TEXT NOT NULL, target_key TEXT NOT NULL, relation TEXT NOT NULL, weight REAL NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL, PRIMARY KEY(user_hash,source_key,target_key,relation))")
            con.execute("CREATE TABLE IF NOT EXISTS predicted_tasks (user_hash TEXT NOT NULL, session_key TEXT NOT NULL, topic_key TEXT NOT NULL, question TEXT NOT NULL, score REAL NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(user_hash,session_key,question))")
            con.commit()

    @staticmethod
    def _user_hash(identity: str) -> str:
        return hashlib.sha256(str(identity or "anonymous").strip().casefold().encode()).hexdigest()

    def _should_research(self, message: str) -> bool:
        text = _clean(message, 4000)
        if not self.enabled or len(text) < 28 or _SKIP.fullmatch(text):
            return False
        if re.search(r"\b(search|research|look up|latest|current|today|verify|sources|compare|what is|how does|why does|explain|build|implement|debug|architecture|price|weather|news)\b", text, re.I):
            return True
        return len(_tokens(text)) >= 6 and "?" in text

    def _freshness(self, query: str) -> int:
        return min(self.max_age, 6 * 3600) if _VOLATILE.search(query) else self.max_age

    def _cached(self, user_hash: str, message: str, limit: int = 5) -> list[dict]:
        q = _tokens(message)
        if not q:
            return []
        now = int(time.time())
        with self._connect() as con:
            rows = con.execute("SELECT * FROM research_cache WHERE user_hash=? AND expires_at>? ORDER BY researched_at DESC LIMIT 250", (user_hash, now)).fetchall()
        ranked = []
        for row in rows:
            overlap = len(q & _tokens(row["query"] + " " + row["title"] + " " + row["snippet"])) / max(1, len(q | _tokens(row["query"])))
            if overlap >= .18:
                ranked.append((overlap * float(row["confidence"]), dict(row)))
        ranked.sort(key=lambda x: (x[0], x[1]["researched_at"]), reverse=True)
        return [r for _, r in ranked[:limit]]

    def context(self, identity: str, message: str, limit: int = 4) -> str:
        """Return only already-cached evidence; never waits for background work."""
        if not identity:
            return ""
        try:
            rows = self._cached(self._user_hash(identity), message, limit)
            if not rows:
                return ""
            lines = ["BACKGROUND RESEARCH CACHE (supporting context; re-check volatile facts):"]
            for r in rows:
                lines.append(f"- {r['title']}: {r['snippet'][:420]} Source: {r['url']} | researched_at={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(r['researched_at']))} | confidence={r['confidence']:.2f}")
            return "\n".join(lines)[:2200]
        except Exception as exc:
            print("[Indo anticipatory cache read]", type(exc).__name__)
            return ""

    def _predictions(self, message: str) -> list[tuple[str, float]]:
        text = _clean(message, 1000)
        low = text.casefold()
        candidates: list[tuple[str, float]] = []
        if re.search(r"\b(build|implement|code|debug|architecture|deploy|api|database)\b", low):
            candidates += [(f"common implementation risks and testing for {text[:110]}", .88), (f"deployment and integration considerations for {text[:110]}", .76)]
        if re.search(r"\b(compare|vs\.?|versus|better|choose|which)\b", low):
            candidates += [(f"trade-offs and decision criteria for {text[:110]}", .84)]
        if re.search(r"\b(what is|explain|how does|why does|meaning)\b", low):
            candidates += [(f"examples and practical applications of {text[:110]}", .72)]
        if _VOLATILE.search(low):
            candidates += [(f"latest developments and source verification for {text[:110]}", .90)]
        if not candidates and len(_tokens(text)) >= 5:
            candidates.append((f"practical examples and next steps for {text[:110]}", .55))
        return sorted(candidates, key=lambda x: x[1], reverse=True)[:2]

    def _upsert_graph(self, user_hash: str, query: str, rows: list[dict], dlm=None, identity: str = ""):
        now = int(time.time())
        labels = list(dict.fromkeys(re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}(?:\s+[A-Z][A-Za-z0-9_-]{2,})?", query)[:8]))
        labels += [r["domain"] for r in rows if r.get("domain")]
        labels = list(dict.fromkeys(x for x in labels if x))[:12]
        keys = [(re.sub(r"\W+", "_", x.casefold()).strip("_")[:90], x[:120]) for x in labels]
        with self._connect() as con:
            for key, label in keys:
                con.execute("INSERT INTO topic_nodes(user_hash,node_key,label,first_seen,last_seen,evidence_count) VALUES(?,?,?,?,?,?) ON CONFLICT(user_hash,node_key) DO UPDATE SET label=excluded.label,last_seen=excluded.last_seen,evidence_count=topic_nodes.evidence_count+1", (user_hash,key,label,now,now,1))
            if keys:
                root = keys[0][0]
                for key, _ in keys[1:]:
                    con.execute("INSERT INTO topic_edges(user_hash,source_key,target_key,relation,weight,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(user_hash,source_key,target_key,relation) DO UPDATE SET weight=topic_edges.weight+1,updated_at=excluded.updated_at", (user_hash,root,key,"co-mentioned",1.0,now))
            con.commit()
        # DLM stores a compact, source-backed public finding in the account's encrypted memory.
        # It is explicitly marked as research, and only snippets with real article URLs qualify.
        if dlm and identity:
            for row in rows[:3]:
                if row.get("url") and row.get("snippet") and row.get("confidence",0) >= .45:
                    fact = f"Research finding: {row['title'][:180]}. {row['snippet'][:500]} Source: {row['url']}"
                    try:
                        dlm.save(identity, fact, category="learning", scope="account", confidence=row["confidence"], importance=.22, source="background_research")
                    except Exception as exc:
                        print("[Indo anticipatory DLM save]", type(exc).__name__)
            if self.cloud_sync:
                try: self.cloud_sync(identity)
                except Exception as exc: print("[Indo anticipatory cloud sync]", type(exc).__name__)

    def _research_job(self, user_hash: str, identity: str, session_key: str, query: str, topic_key: str, generation: str, dlm=None) -> int:
        try:
            raw = self.research_fn(query) or []
        except Exception as exc:
            print("[Indo anticipatory research]", type(exc).__name__)
            return 0
        # A running network request cannot always be interrupted; discard its result
        # before persistence if a newer, unrelated topic superseded this session job.
        if generation != "prediction":
            with self.lock:
                current = self.jobs.get(session_key)
                if current and current.get("generation") != generation:
                    return 0
        now = int(time.time())
        ttl = self._freshness(query)
        normalized = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            url = _clean(item.get("url"), 1000)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or url in seen:
                continue
            # Research results are metadata, not fetch instructions. Reject local/private
            # destinations so a future fetcher cannot accidentally turn cache data into SSRF.
            host = (parsed.hostname or "").rstrip(".").casefold()
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
                continue
            try:
                ip = ipaddress.ip_address(host.strip("[]"))
                if not ip.is_global:
                    continue
            except ValueError:
                if not re.fullmatch(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
                    continue
            engine = _clean(item.get("engine"), 80)
            if engine.casefold() in {"google search", "bing search", "duckduckgo search", "wikipedia search"}:
                continue
            seen.add(url)
            title = _clean(item.get("title") or item.get("name") or parsed.netloc, 300)
            snippet = _clean(item.get("snippet") or item.get("description") or item.get("summary"), 1000)
            if not snippet:
                continue
            domain = (parsed.hostname or "").lower().removeprefix("www.")
            confidence = .38
            if title and snippet: confidence += .18
            if len(snippet) > 120: confidence += .10
            if domain and not any(x in domain for x in ("google.com", "bing.com", "duckduckgo.com")): confidence += .12
            if item.get("published") or item.get("date"): confidence += .08
            confidence = min(.86, confidence)
            normalized.append({"title":title,"snippet":snippet,"url":url,"domain":domain,"confidence":confidence,"engine":engine})
        with self._connect() as con:
            for row in normalized[:15]:
                con.execute("INSERT INTO research_cache(id,user_hash,topic_key,query,title,snippet,url,domain,confidence,researched_at,expires_at,source_engine) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex,user_hash,topic_key,query,row["title"],row["snippet"],row["url"],row["domain"],row["confidence"],now,now+ttl,row["engine"]))
            con.execute("DELETE FROM research_cache WHERE expires_at<?", (now - 86400,))
            con.commit()
        with self.lock:
            current = self.jobs.get(session_key)
            still_relevant = not current or current.get("generation") == generation
        if still_relevant and normalized:
            self._upsert_graph(user_hash, query, normalized, dlm=dlm, identity=identity)
        return len(normalized)

    def _run_prediction(self, user_hash: str, session_key: str, topic_key: str, question: str, score: float, job_key: str = ""):
        # Predictive preparation is deliberately low priority and reuses existing cache.
        if self._cached(user_hash, question, 2):
            status = "reused_cache"
        else:
            status = "prepared"
            try:
                self._research_job(user_hash, "", job_key or session_key, question, topic_key, "prediction", dlm=None)
            except Exception:
                status = "failed"
        with self._connect() as con:
            con.execute("INSERT OR REPLACE INTO predicted_tasks(user_hash,session_key,topic_key,question,score,status,created_at) VALUES(?,?,?,?,?,?,?)", (user_hash,session_key,topic_key,question,score,status,int(time.time())))
            con.commit()

    def start(self, identity: str, session_key: str, message: str) -> dict[str, Any]:
        """Schedule research/predictions and return immediately."""
        if not identity or not self._should_research(message):
            return {"started": False, "reason": "not_researchable"}
        user_hash = self._user_hash(identity)
        # Namespace in-memory cancellation keys by account. Two accounts may use
        # the same browser/session identifier and must never cancel each other's work.
        session_key = _clean(session_key or user_hash, 160)
        job_key = user_hash + ":" + session_key
        topic_key = _topic_key(message)
        cached = self._cached(user_hash, message, 3)
        # Cancel previous session work when topic overlap is low.
        generation = uuid.uuid4().hex
        with self.lock:
            old = self.jobs.get(job_key)
            if old:
                old_terms, new_terms = _tokens(old.get("topic", "")), _tokens(message)
                overlap = len(old_terms & new_terms) / max(1, len(old_terms | new_terms))
                if overlap < .18:
                    for future in old.get("futures", []):
                        future.cancel()
            futures: list[Future] = []
            self.jobs[job_key] = {"generation":generation,"topic":message[:500],"futures":futures,"started":time.time()}
        # Fresh cache avoids duplicate primary search; stale cache is refreshed asynchronously.
        fresh_match = bool(cached) and not _VOLATILE.search(message)
        if not fresh_match:
            future = self.pool.submit(self._research_job, user_hash, identity, job_key, message[:500], topic_key, generation, self.dlm)
            futures.append(future)
        predictions = self._predictions(message)
        # Queue only the single highest-value follow-up to cap background API/search load.
        if predictions:
            question, score = predictions[0]
            with self._connect() as con:
                con.execute("INSERT OR REPLACE INTO predicted_tasks(user_hash,session_key,topic_key,question,score,status,created_at) VALUES(?,?,?,?,?,?,?)", (user_hash,session_key,topic_key,question,score,"queued",int(time.time())))
                con.commit()
            if not self._cached(user_hash, question, 2):
                futures.append(self.pool.submit(self._run_prediction, user_hash, session_key, topic_key, question, score, job_key))
        return {"started": bool(futures), "cache_reused": bool(cached), "predictions_queued": min(1, len(predictions)), "topic": topic_key}

    def graph(self, identity: str, limit: int = 40) -> dict[str, Any]:
        if not identity: return {"nodes":[],"edges":[]}
        uh = self._user_hash(identity)
        with self._connect() as con:
            nodes = [dict(r) for r in con.execute("SELECT node_key,label,first_seen,last_seen,evidence_count FROM topic_nodes WHERE user_hash=? ORDER BY last_seen DESC LIMIT ?",(uh,max(1,min(limit,100))))]
            edges = [dict(r) for r in con.execute("SELECT source_key,target_key,relation,weight,updated_at FROM topic_edges WHERE user_hash=? ORDER BY weight DESC LIMIT ?",(uh,max(1,min(limit*2,200))))]
        # Rehydrate graph facts from encrypted DLM so graph knowledge survives
        # ephemeral Render restarts via the existing Supabase DLM snapshot.
        if self.dlm:
            try:
                identity = str(identity or "")
                for memory in self.dlm.list_all(identity, limit=500):
                    for entity in memory.get("entities", []):
                        key = re.sub(r"\W+", "_", str(entity).casefold()).strip("_")[:90]
                        if key and not any(n["node_key"] == key for n in nodes):
                            nodes.append({"node_key":key,"label":str(entity)[:120],"first_seen":memory.get("created_at",0),"last_seen":memory.get("updated_at",0),"evidence_count":1})
                    for relation in memory.get("relations", []):
                        subject = str(relation.get("subject", "user"))
                        obj = str(relation.get("object", ""))
                        target = re.sub(r"\W+", "_", obj.casefold()).strip("_")[:90]
                        if target:
                            if not any(n["node_key"] == target for n in nodes):
                                nodes.append({"node_key":target,"label":obj[:120],"first_seen":memory.get("created_at",0),"last_seen":memory.get("updated_at",0),"evidence_count":1})
                            edge = {"source_key":subject,"target_key":target,"relation":str(relation.get("predicate", "related_to")),"weight":1.0,"updated_at":memory.get("updated_at",0)}
                            if not any(e["source_key"] == edge["source_key"] and e["target_key"] == target and e["relation"] == edge["relation"] for e in edges):
                                edges.append(edge)
            except Exception as exc:
                print("[Indo anticipatory graph/DLM]", type(exc).__name__)
        return {"nodes":nodes[:max(1,min(limit,100))],"edges":edges[:max(1,min(limit*2,200))]}

    def status(self) -> dict[str, Any]:
        with self.lock:
            active = sum(1 for j in self.jobs.values() for f in j.get("futures",[]) if not f.done())
        now = int(time.time())
        try:
            with self._connect() as con:
                cached = int(con.execute("SELECT COUNT(*) FROM research_cache WHERE expires_at>?", (now,)).fetchone()[0])
                outdated = int(con.execute("SELECT COUNT(*) FROM research_cache WHERE expires_at<=?", (now,)).fetchone()[0])
                prepared = int(con.execute("SELECT COUNT(*) FROM predicted_tasks WHERE status IN ('prepared','reused_cache')").fetchone()[0])
        except Exception:
            cached = outdated = prepared = 0
        return {"enabled":self.enabled,"active_background_jobs":active,"cache_ttl_seconds":self.max_age,
                "cached_findings":cached,"outdated_findings":outdated,"prepared_followups":prepared,"workers":2}

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)

import time

from indo_anticipatory import AnticipatoryIntelligenceEngine


class FakeDLM:
    def __init__(self):
        self.saved = []

    def save(self, identity, text, **kwargs):
        self.saved.append((identity, text, kwargs))
        return {"saved": True}

    def list_all(self, identity, limit=500):
        return []


def wait_for_idle(engine, timeout=4):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if engine.status()["active_background_jobs"] == 0:
            return
        time.sleep(.02)
    raise AssertionError("background research did not finish in time")


def test_social_message_is_not_researched(tmp_path):
    calls = []
    engine = AnticipatoryIntelligenceEngine(tmp_path, lambda q: calls.append(q) or [])
    try:
        assert engine.start("user-1", "s1", "hey") == {"started": False, "reason": "not_researchable"}
        assert not calls
    finally:
        engine.close()


def test_background_cache_graph_and_dlm_integration(tmp_path):
    dlm = FakeDLM()
    calls = []

    def research(query):
        calls.append(query)
        return [{
            "title": "FastAPI background task documentation",
            "snippet": "FastAPI background tasks can execute work after a response has been sent.",
            "url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
            "engine": "Google",
        }]

    engine = AnticipatoryIntelligenceEngine(tmp_path, research, dlm=dlm)
    try:
        result = engine.start("user-1", "session-1", "How should I implement background research in FastAPI without blocking chat streaming?")
        assert result["started"] is True
        wait_for_idle(engine)
        context = engine.context("user-1", "How should I implement background research in FastAPI without blocking chat streaming?")
        graph = engine.graph("user-1")
        assert "fastapi.tiangolo.com" in context
        assert graph["nodes"]
        assert dlm.saved
        assert calls
    finally:
        engine.close()


def test_private_and_local_source_urls_are_rejected(tmp_path):
    def research(query):
        return [
            {"title": "Local service", "snippet": "Should not be cached", "url": "http://127.0.0.1/admin"},
            {"title": "Public source", "snippet": "A valid public source with enough detail to cache.", "url": "https://example.org/article"},
        ]
    engine = AnticipatoryIntelligenceEngine(tmp_path, research)
    try:
        engine.start("user-1", "s1", "How should I design a robust background research service for a web application?")
        wait_for_idle(engine)
        context = engine.context("user-1", "background research service web application")
        assert "127.0.0.1" not in context
        assert "example.org" in context
    finally:
        engine.close()


def test_same_session_key_different_accounts_do_not_share_job_cancellation(tmp_path):
    import threading
    gates = {"a": threading.Event(), "b": threading.Event()}
    def research(query):
        key = "a" if "alpha" in query else "b"
        gates[key].wait(1)
        return [{"title": key, "snippet": "public evidence for " + key, "url": f"https://{key}.example.org/source"}]
    engine = AnticipatoryIntelligenceEngine(tmp_path, research)
    try:
        engine.start("account-a", "same-session", "How can alpha research workers safely process independent tasks in background?")
        engine.start("account-b", "same-session", "How can beta research workers safely process independent tasks in background?")
        gates["a"].set(); gates["b"].set()
        wait_for_idle(engine)
        assert engine.context("account-a", "alpha research workers")
        assert engine.context("account-b", "beta research workers")
    finally:
        engine.close()

# Indo AI — Anticipatory Intelligence (Levels 1–3)

## What is integrated

### Level 1 — Topic Awareness
- Detects substantive topics from normal signed-in text conversations.
- Schedules public web research on a bounded background pool (two workers).
- Stores source title, snippet, URL, domain, engine, research timestamp, expiry and a heuristic confidence score.
- Cancels queued work for an unrelated newer topic in the same session; if a network call is already running, its obsolete result is discarded before persistence.
- The chat request never awaits research. It can only read completed cache entries, with a short SQLite lock timeout.

### Level 2 — Predictive Preparation
- Generates and ranks likely next questions using topic/intent patterns.
- Queues only the highest-value follow-up to control search load.
- Reuses fresh cached evidence instead of searching again.
- Prepares evidence packs, not fabricated model answers; Indo answers the actual follow-up using the normal response pipeline.

### Level 3 — Continuous Knowledge Building
- Builds per-account topic nodes and co-mention relationships.
- Expires volatile findings sooner and refreshes them on a later relevant request.
- Saves source-backed findings as low-importance `learning` records in encrypted, account-scoped DLM.
- Calls the existing DLM cloud sync after successful research-memory writes.
- Reconstructs graph nodes/relations from DLM so knowledge can survive ephemeral Render restarts through the existing Supabase snapshot.

## New module and endpoints

- `indo_anticipatory.py` — engine, cache, task scheduler, graph.
- `GET /api/anticipatory/status` — signed-in operational status and cache freshness counts.
- `GET /api/anticipatory/graph?limit=40` — signed-in account's topic graph.

## Environment

```env
INDO_ANTICIPATORY_ENABLED=1
INDO_RESEARCH_CACHE_TTL=86400
```

Set `INDO_ANTICIPATORY_ENABLED=0` to disable. Volatile topics use a shorter six-hour cache lifetime. Explicit Research mode continues to use Indo's existing foreground research pipeline to avoid duplicating its primary search.

## Important boundaries

- Research results are public-source evidence, not guaranteed truth. Confidence is a heuristic ranking signal, not a calibrated probability.
- Only source-backed snippets with real HTTP(S) URLs are cached; search-engine fallback links are excluded.
- Running network calls cannot be forcibly killed by Python threads. Queued work is cancelled and stale running results are discarded.
- Local research cache/graph is a performance layer. Encrypted DLM is the account persistence path; keep `INDO_SESSION_SECRET` stable and configured.

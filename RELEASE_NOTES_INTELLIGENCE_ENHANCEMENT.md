# Indo AI — Intelligence Systems Enhancement

This package combines the six intelligence systems with the existing v18.10.5 application and its `indo_brain/` and `indo_core/` packages.

## Enhancements in this build

- **Anticipatory Intelligence:** account-namespaced background-job cancellation; rejects localhost, private and non-global IP source URLs before caching; keeps chat streaming independent of research workers.
- **Adaptive Persona Sync:** a new explicit preference replaces the previous persona preference set, avoiding contradictory long-lived instructions. Current-turn cues remain temporary.
- **Cross-Session Project Threads:** account-scoped deletion of a single event or an entire project thread; event listing includes event IDs for user-directed deletion; broader secret-keyword filtering.
- **Devil's Advocate:** retained as opt-in critical-review guidance.
- **Autonomous Execution:** account-scoped workflow cancellation and deletion; approval gates remain; no arbitrary shell/code or external side effects are executed. When Supabase and encrypted DLM are configured, workflow snapshots are encrypted and synced to the existing per-account state table; imports are account-bound and merge without replacing newer local records.
- **Hyper-Local Intelligence:** validates timezone names against the installed IANA timezone database; location remains coarse and user-entered, with no device geolocation.
- **Unified Intelligence Core:** lightweight feature-readiness and background-research status endpoint.

## New endpoints

- `GET /api/indo-intelligence/status` — signed-in feature health overview.
- `DELETE /api/projects/threads/{project_name}` — delete the signed-in user's project thread.
- `POST /api/indo-autonomy/executions/{workflow_id}/cancel` — cancel an unfinished owned workflow.

Existing endpoints and feature modules are retained.

## Validation performed

- Python compilation for the main app and all six feature modules plus the unified core.
- Full local pytest suite: **99 passed, 6 warnings**.
- FastAPI application import: succeeded; unified core reported 7/7 components available in this local environment.

These are local checks only. Live Google OAuth, external AI provider calls, live web research, Supabase read/write, Render restart persistence, and production deployment were not tested.

## Deployment safety

- No `.env`, API keys, session secret files, private keys, SQLite databases, or runtime caches are included.
- Preserve existing Render environment variables, especially `INDO_SESSION_SECRET`; do not regenerate it during deployment.
- Apply reviewed Supabase SQL migrations separately; this package does not connect to or modify the user's Supabase project.
- Workflow tracking uses the configured application data directory as a local cache. With `INDO_SUPABASE_URL`, `INDO_SUPABASE_SECRET_KEY`, and a stable `INDO_SESSION_SECRET` configured, encrypted workflow snapshots sync to Supabase. Without those settings, workflow records remain local and may not survive ephemeral-host restarts.

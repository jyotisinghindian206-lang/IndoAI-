# Cross-Session Project Threads

This feature records explicit project decisions, milestones, and relevant completed-chat checkpoints in an account-scoped thread store.

## Integration
- Module: `indo_project_threads.py`
- Runtime database: `INDO_DATA_DIR/indo_project_threads.sqlite3` (local cache)
- Authenticated endpoints: `GET /api/projects/threads` and `GET /api/projects/threads/{project_name}`
- Chat context is injected only when a project hint matches the current message or recent user history.
- Events are synchronized to Supabase state type `project_threads_v1` as an encrypted snapshot using the existing DLM Fernet cipher. SQLite is a cache, not the durable cloud source.

## Requirements
- Existing DLM encryption must be available (`cryptography` dependency).
- Configure `INDO_SUPABASE_URL` and `INDO_SUPABASE_SECRET_KEY` on the server. The key must never be exposed to the browser or committed.
- Keep `INDO_SESSION_SECRET` stable across deployments; it is used by the existing DLM encryption setup.
- The existing `indo_user_state` table and RLS policy must permit server-side `service_role` access. This feature uses a new `state_type` value: `project_threads_v1`.

## Safety and scope
- Project threads are isolated by authenticated account hash.
- Cloud snapshots are encrypted before being stored in Supabase.
- The engine records explicit decisions/milestones and bounded checkpoints; it does not execute tasks or make decisions on the user's behalf.
- Passwords, tokens, API keys and secret-like messages are excluded by a conservative filter.
- Cloud sync failures are logged and do not block chat streaming.

## Validation
Run `pytest -q`. Supabase network sync still requires deployment credentials and has not been live-tested as part of this package build.

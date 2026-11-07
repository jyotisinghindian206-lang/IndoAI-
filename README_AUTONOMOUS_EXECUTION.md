# Indo AI — Multi-Step Autonomous Execution

This integration adds an account-scoped workflow planner and progress tracker.

## API

- `POST /api/indo-autonomy/executions` — create a proposed workflow from `{ "goal": "..." }`.
- `GET /api/indo-autonomy/executions` — list the signed-in account's workflows.
- `POST /api/indo-autonomy/executions/{workflow_id}/approve` — approve the plan before progress can advance.
- `POST /api/indo-autonomy/executions/{workflow_id}/steps` — update a step with `{ "step_id": "step_1", "status": "in_progress|completed|blocked|skipped", "result": "..." }`.

All endpoints require the existing Indo account session. Workflow records are isolated by a SHA-256 account identifier in a local SQLite database under `INDO_DATA_DIR`.

## Safety and execution boundary

This module plans and tracks work; it does **not** run arbitrary code, shell commands, deployments, purchases, messages, or other external side effects. Consequential steps are explicitly marked and blocked by the tracker. A future connector must have its own scoped permissions, user confirmation, audit trail, and rollback strategy before it can perform external actions.

## Validation

The integrated project test suite was run in the build environment: 86 passed. Python compilation passed for `indo.py` and `indo_autonomous_execution.py`. The existing FastAPI `on_event` deprecation warnings remain. Live Render/Supabase deployment was not tested.

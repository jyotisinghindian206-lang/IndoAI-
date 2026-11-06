# INDO AI — DYNAMIC LEARNING MEMORY (DLM)
## Version 18.10.0 — Complete Implementation Guide

### 1. Overview

Indo AI's Dynamic Learning Memory (DLM) is an account-scoped memory system designed to preserve useful context across conversations.

It supports automatic knowledge extraction, project continuity, preference learning, semantic retrieval, memory management, and temporal indexing.

This update covers all 18 planned DLM capabilities.

**Important:** This is an update to the existing Indo AI application, not a standalone replacement for the entire repository.

---

### 2. Required Files

The update package contains:

- `indo.py` — complete updated main application.
- `indo_dlm.py` — encrypted Dynamic Learning Memory module.
- `README_DLM.md` — implementation and configuration guide.

Keep the following existing project components:

- `indo_brain/`
- `indo_core/`
- Static assets and templates.
- Existing environment configuration.
- Existing persistent data directory.
- Other application modules and integrations.

Do not delete existing databases or user data.

---

### 3. Installation

1. Back up your existing `indo.py` and `indo_dlm.py`.
2. Extract the latest Indo AI v18.10.0 update package.
3. Replace your existing `indo.py` with the updated version.
4. Replace or add `indo_dlm.py` beside `indo.py`.
5. Preserve all existing project folders and assets.
6. Install any missing dependencies using your existing requirements file.
7. Start Indo AI and sign in using your existing account.

**Important:** Use the latest v18.10.0 package as the integrated source. Do not mix the older v18.9.0 files with the newer files.

---

### 4. DLM Feature Registry — All 18 Features

#### A. Knowledge Extraction and Intelligence

**1. Automatic Knowledge Extraction**
- Extracts clear, useful first-person facts from ordinary text conversations.
- Avoids additional Gemini/OpenAI calls for extraction.
- Excludes selected sensitive information.

**2. Project and Task Memory**
- Stores project-related context.
- Preserves task information.
- Supports project-scoped retrieval.

**3. Preference Detection**
- Captures explicit preferences.
- Stores relevant habits, roles, and learning context.
- Uses saved preferences to guide future responses.

**4. Entity and Relationship Mapping**
- Stores entity and relationship metadata alongside memory records.
- Helps connect relevant pieces of information.

**5. Memory Compression**
- Removes exact duplicate records.
- Preserves distinct information.
- Avoids unnecessary repeated storage.

**6. Contradiction and Recency Resolution**
- Detects selected conflicting fact slots.
- Uses narrow replacement rules.
- Avoids broad, unsafe fuzzy overwrites.

**7. Semantic Retrieval**
- Supports local synonym-assisted retrieval.
- Does not require Gemini/OpenAI API calls for ordinary memory searches.
- Can optionally use sentence-transformer embeddings.

**8. Importance and Memory Decay**
- Uses recency and importance when ranking memories.
- Supports age-aware pruning when account memory limits are reached.

#### B. Privacy and Context Management

**9. Memory Importance and Decay**
- Prioritizes useful, recent information.
- Helps prevent old, less relevant memories from dominating retrieval.

**10. Memory Dashboard and User Controls**
- Existing memory dashboard is retained.
- Supports category controls.
- Supports individual memory deletion.
- Supports clearing and exporting memory.
- Adds chronological timeline access.

**11. Cross-Session Project Continuity**
- Retrieves relevant project memories across conversations.
- Uses the same authenticated account.
- Uses project labels to scope continuity.

**12. Dynamic Context Retrieval**
- Retrieves relevant memories for the current request.
- Adds matching project context.
- Keeps ordinary memory retrieval local.

**13. Multi-Turn Reference Resolution**
- Enriches obvious follow-up queries using recent turns from the same conversation.
- Helps resolve references such as "that project" or "the previous task."

**14. Session Conflict Isolation**
- Uses conversation boundaries when enriching context.
- Keeps authenticated account identity as the primary security boundary.
- Does not treat a browser conversation ID as authentication.

#### C. Personalization and Optimization

**15. Adaptive Communication**
- Uses relevant saved preferences and learning context.
- Provides bounded response guidance.
- Gives current user instructions priority over stored preferences.

**16. Proactive Follow-Up Suggestions**
- Generates optional suggestions from saved tasks and goals.
- Supports pull-based follow-up retrieval.
- Does not independently send notifications or messages.

**17. Context-Aware Tool Selection**
- Uses relevant project and task context to guide tool selection.
- Gives explicit user intent priority.
- Does not guarantee that a particular tool will be invoked.

**18. Temporal Memory Indexing**
- Supports chronological memory retrieval.
- Uses stored creation and update timestamps.
- Allows filtering by time range and category.

---

### 5. API Endpoints

The updated DLM exposes the following authenticated endpoints:

**Memory timeline**

`GET /api/memory/timeline?start=<unix>&end=<unix>&category=task&limit=100`

Retrieves memories within a specified time range.

**Project memory**

`GET /api/memory/project/{project_name}?limit=40`

Retrieves memories associated with a project.

**Follow-up suggestions**

`GET /api/memory/followups?project=orion&limit=5`

Retrieves optional task and goal suggestions.

All endpoints require the existing signed-in account session and return private, no-store responses.

---

### 6. Security and Privacy

DLM is designed around the following safeguards:

- Account-scoped memory.
- Encryption at rest.
- Authentication through the existing application session.
- Sensitive-information exclusion during automatic extraction.
- Memory category controls.
- Individual deletion and full-clear functionality.
- Private API responses.
- No reliance on client-supplied email as the account identity.

Do not expose API keys, passwords, session secrets, or encryption credentials.

#### Important encryption configuration

Set a stable environment variable:

`INDO_SESSION_SECRET`

Use a strong secret of at least 32 characters.

Keep this value unchanged across deployments.

DLM encryption keys are derived from this secret. Losing or rotating it can make existing encrypted memory records unreadable.

Never commit this secret to GitHub or share it publicly.

---

### 7. Storage and Deployment

Indo AI must use persistent storage for reliable memory across restarts and deployments.

For Render:

- Configure a persistent disk.
- Use the existing application data mount, expected at `/var/data`.
- Preserve existing databases.
- Keep the encryption secret stable.
- Verify database access after deployment.

Without persistent storage, locally stored SQLite memory may be lost during redeployments.

---

### 8. Optional Semantic Embeddings

The default DLM retrieval system uses local synonym-assisted lexical retrieval.

Optional vector retrieval can be enabled using a locally installed sentence-transformer model.

Environment variable:

`INDO_DLM_EMBEDDING_MODEL`

This optional configuration may require substantial additional CPU, RAM, and storage.

It is not included as a default dependency because of its potential deployment cost.

---

### 9. Validation and Testing

The update's focused validation covered:

- Python syntax compilation.
- Encryption at rest.
- Account isolation.
- Project scoping.
- Duplicate compression.
- Preference replacement.
- Sensitive-data rejection.
- Relationship metadata.
- Memory retrieval.
- Cross-session project retrieval.
- Timeline filtering.
- Task follow-up suggestions.
- Same-session reference enrichment.
- Disabled-memory behavior.

**Testing limitation:** Focused tests are not equivalent to a complete application test.

The full Indo AI application was not launched in the validation environment. Render deployment, browser dashboard behavior, live authentication, provider-backed tool routing, and end-to-end persistence must still be tested.

---

### 10. Recommended Integration Test

After installation, test the following:

1. Sign in to Indo AI.
2. Save a harmless project preference.
3. Start a new conversation.
4. Ask Indo AI to recall the project context.
5. Check the memory dashboard.
6. Check the project timeline.
7. Test an individual memory deletion.
8. Restart the application.
9. Sign in again and check persistence.
10. Verify that another account cannot access the first account's memories.

Also test existing Indo AI features, including:

- Google login.
- Chat history.
- Gemini integration.
- OpenAI integration.
- Indo Music Player.
- File uploads.
- Image generation.
- Voice features.
- Research tools.

Do not consider the integration complete until these tests pass.

---

### 11. Version Information

**Product:** Indo AI — Intelligent Neoteric Disruptive Operator

**Update:** v18.10.0

**Module:** Dynamic Learning Memory

**Coverage:** Steps 1–18

**Architecture:** Hybrid DLM with separate integration architecture.

**Deployment target:** Existing Indo AI application.

**Status:** Implementation package prepared; full end-to-end application verification remains pending.

---

### 12. Final Note

DLM is intended to make Indo AI better at retaining useful context, understanding ongoing projects, adapting to preferences, and retrieving relevant information across conversations.

It is not unlimited memory, perfect autonomous learning, or guaranteed self-improvement.

Its reliability depends on correct integration, persistent storage, encryption configuration, account authentication, and successful end-to-end testing.

**INDO AI — Intelligence Beyond Limits.**

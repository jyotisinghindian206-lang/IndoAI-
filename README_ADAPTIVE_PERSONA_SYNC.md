# Adaptive Persona Sync

Indo AI now adapts its response style using two distinct signal types:

1. **Persistent preferences:** only clear, explicit communication instructions are saved (for example, “please keep it short” or “explain in detail from now”). These are stored through the existing encrypted, account-scoped DLM using `category=preference` and `source=persona_sync`, so they follow the signed-in account through the existing cloud DLM snapshot path.
2. **Current-turn cues:** task and phrasing cues (such as a request for step-by-step explanation or a brief casual greeting) affect only the current response. They are not saved as permanent traits.

The module does not infer sensitive traits or emotional states. It does not use provider calls, does not block streaming, and fails open: if profile retrieval fails, the chat continues with ordinary prompt rules.

## Files
- `indo_persona_sync.py` — explicit preference extraction and compact profile builder.
- `indo.py` — integrates profile context into both the normal and ultra-fast prompt paths, and syncs explicit preference updates through DLM.
- `tests/test_persona_sync.py` — tests explicit preference detection, temporary cues, and account separation.

No new environment variables are required. The feature uses the existing DLM encryption and stable `INDO_SESSION_SECRET` configuration.

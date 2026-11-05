# Indo AI v18.3 — complete Render source package

This package contains the v18.3 application entry point and the Python modules it imports.

## Included

- `indo.py` — FastAPI application (v18.3 identity/model update)
- `indo_brain/` — reasoning, completion, GARUDA, VISHNU, knowledge and evaluation modules
- `indo_core/` — optional configuration, diagnostics, prompt and input-guard modules
- `requirements.txt` — Python runtime dependencies
- `.env.example` — names of optional environment variables; no credentials
- `tests/` — compatible regression tests
- `Procfile` — Render start command

## Render setup

Build command:

```sh
pip install -r requirements.txt
```

Start command:

```sh
uvicorn indo:app --host 0.0.0.0 --port $PORT
```

Recommended Render environment settings:

- `INDO_PROVIDERS=gemini,openai,ollama`
- `INDO_PRIMARY_PROVIDER=gemini`
- `INDO_OLLAMA_ENABLED=1`
- `INDO_OLLAMA_MODE=cloud`
- Set the provider keys you actually use: `GEMINI_API_KEY`, `INDO_OPENAI_API_KEY`, `INDO_OLLAMA_API_KEY`.
- For Google sign-in, set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and optionally `GOOGLE_REDIRECT_URI`. The callback path is `/auth/google/callback`.
- For stable sessions and user data, attach a Render persistent disk mounted at `/var/data`, then set `INDO_DATA_DIR=/var/data` and `INDO_SESSION_SECRET` (at least 32 characters).

## Safe replacement instructions

1. Back up the current GitHub repository and Render persistent disk first.
2. Replace the app source files with the contents of this package. The root must contain `indo.py`, `indo_brain/`, `indo_core/`, and `requirements.txt`.
3. Keep your existing Render environment variables; do not replace them with blank `.env.example` values.
4. **Do not delete or overwrite your persistent data**: account/chat databases, `IndoAuthData`, profile photos, uploads, saved music, or the existing `INDO_SESSION_SECRET`. These belong on the persistent disk, not in this source ZIP.
5. Commit and push the files; Render should build and start the service.

The package deliberately contains no `.env`, API keys, OAuth secrets, session key, database, profile, upload, or music data.

## Local checks

```sh
python -m compileall -q indo.py indo_brain indo_core tests
INDO_DATA_DIR=/tmp/indo-test python -m unittest discover -s tests -v
```

Local verification for this package: application import succeeded and loaded 86 FastAPI routes; Python compilation succeeded; 68 compatible regression tests passed. Live provider requests, OAuth, music playback, voice, image generation, browser workflows and an actual Render deployment were not tested.

Note: `torch` and `diffusers` are intentionally not installed by the Render requirements because they are large optional local-GPU image-generation dependencies. Hosted image providers remain separately configurable.

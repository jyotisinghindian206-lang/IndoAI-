# Indo AI — Hyper-Local Intelligence

Hyper-local context is opt-in and account-scoped. Indo never reads browser/device geolocation. The user may explicitly save a coarse city/region, preferred response language, secondary languages, and timezone.

## API

- `GET /api/indo-hyperlocal/profile` — read the signed-in user's preferences.
- `PUT /api/indo-hyperlocal/profile` — update preferences with `{ "enabled": true, "city": "Gurugram", "region": "Haryana", "country": "India", "language": "hinglish", "secondary_languages": ["english", "hindi"], "timezone": "Asia/Kolkata" }`.

Supported language values: `auto`, `english`, `hinglish`, `hindi`, `bengali`, `tamil`, `telugu`, `marathi`, `gujarati`, `punjabi`, `kannada`, `malayalam`, `odia`, `assamese`, `urdu`.

The location fields accept coarse place names only; numeric coordinates, street/house-like details and URLs are rejected. `enabled: false` disables personalized location context. Profiles are isolated by a SHA-256 hash of the authenticated Indo account identity and stored in `indo_hyperlocal.sqlite3` under `INDO_DATA_DIR`.

The engine provides cultural/language context only. It does not invent live weather, traffic, opening hours, prices or local events; those require live verification through the app's research/search facilities.

## Privacy and limitations

- No device location permission is requested or accessed.
- Location is user-entered and optional.
- Preferences are cached in the app data directory SQLite database and, when the existing Supabase connection and DLM encryption are configured, synced as encrypted state type `hyperlocal_profile_v1`. Live cloud sync was not tested in this build environment.
- Language detection is lightweight heuristic detection; explicit profile and current-turn instructions take precedence.

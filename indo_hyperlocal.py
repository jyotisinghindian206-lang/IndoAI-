"""Permission-based Indian and regional context for Indo AI.

No device geolocation is read. A user must explicitly opt in and provide a
coarse city/region and language preferences. Precise addresses/coordinates are
rejected; the module only supplies context and never claims live local facts.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
from typing import Any

_LANGS = {"english", "hinglish", "hindi", "bengali", "tamil", "telugu", "marathi", "gujarati", "punjabi", "kannada", "malayalam", "odia", "assamese", "urdu"}
_REGION = re.compile(r"^[\w ,.'()/-]{0,100}$", re.UNICODE)


def _account(identity: str) -> str:
    return hashlib.sha256(str(identity).strip().casefold().encode()).hexdigest()


def infer_language(text: str) -> str:
    s = str(text or "")
    if re.search(r"[\u0900-\u097F]", s):
        return "hindi"
    if re.search(r"\b(kya|kaise|hai|hain|bhai|yaar|mujhe|nahi|haan|karna|batao|bro)\b", s, re.I):
        return "hinglish"
    if re.search(r"[\u0980-\u09FF]", s): return "bengali"
    if re.search(r"[\u0B80-\u0BFF]", s): return "tamil"
    if re.search(r"[\u0C00-\u0C7F]", s): return "telugu"
    if re.search(r"[\u0A80-\u0AFF]", s): return "gujarati"
    if re.search(r"[\u0C80-\u0CFF]", s): return "kannada"
    if re.search(r"[\u0D00-\u0D7F]", s): return "malayalam"
    return "english"


class HyperLocalIntelligence:
    def __init__(self, data_dir: str | Path):
        root = Path(data_dir); root.mkdir(parents=True, exist_ok=True)
        self.path = root / "indo_hyperlocal.sqlite3"
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS profiles(account TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, city TEXT NOT NULL DEFAULT '', region TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT 'India', language TEXT NOT NULL DEFAULT 'auto', secondary_languages TEXT NOT NULL DEFAULT '[]', timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata', updated_at INTEGER NOT NULL)")
            db.commit()

    def _db(self):
        db = sqlite3.connect(str(self.path), timeout=8)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=8000")
        return db

    @staticmethod
    def _coarse(value: str, label: str) -> str:
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(value) > 100 or not _REGION.fullmatch(value) or re.search(r"\d{2,}|@|://", value):
            raise ValueError(f"{label} must be a coarse city/region name, not an address or coordinates")
        return value

    def get(self, identity: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM profiles WHERE account=?", (_account(identity),)).fetchone()
        if not row:
            return {"enabled": False, "city": "", "region": "", "country": "India", "language": "auto", "secondary_languages": [], "timezone": "Asia/Kolkata"}
        return {"enabled": bool(row["enabled"]), "city": row["city"], "region": row["region"], "country": row["country"], "language": row["language"], "secondary_languages": json.loads(row["secondary_languages"]), "timezone": row["timezone"]}

    def update(self, identity: str, data: dict[str, Any]) -> dict[str, Any]:
        if not identity: raise ValueError("Sign in required")
        old = self.get(identity)
        enabled = bool(data.get("enabled", old["enabled"]))
        city = self._coarse(data.get("city", old["city"]), "City")
        region = self._coarse(data.get("region", old["region"]), "Region/state")
        country = self._coarse(data.get("country", old["country"]), "Country") or "India"
        language = str(data.get("language", old["language"])).strip().lower()
        if language != "auto" and language not in _LANGS: raise ValueError("Unsupported language preference")
        secondary = data.get("secondary_languages", old["secondary_languages"])
        if not isinstance(secondary, list) or len(secondary) > 5 or any(str(x).lower() not in _LANGS for x in secondary): raise ValueError("Choose up to five supported secondary languages")
        timezone = str(data.get("timezone", old["timezone"])).strip()[:64]
        if not re.fullmatch(r"[A-Za-z_+-]+(?:/[A-Za-z0-9_+.-]+)*", timezone): raise ValueError("Invalid timezone identifier")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone identifier")
        now = int(time.time())
        with self._db() as db:
            db.execute("INSERT INTO profiles VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(account) DO UPDATE SET enabled=excluded.enabled,city=excluded.city,region=excluded.region,country=excluded.country,language=excluded.language,secondary_languages=excluded.secondary_languages,timezone=excluded.timezone,updated_at=excluded.updated_at", (_account(identity), int(enabled), city, region, country, language, json.dumps([str(x).lower() for x in secondary]), timezone, now))
            db.commit()
        return self.get(identity)

    def context(self, identity: str, message: str) -> str:
        profile = self.get(identity)
        detected = infer_language(message)
        chosen = profile["language"] if profile["language"] != "auto" else detected
        bits = ["HYPER-LOCAL CONTEXT (user-controlled preferences):"]
        if profile["enabled"]:
            if profile["city"] or profile["region"]:
                bits.append("Coarse location supplied by user: " + ", ".join(x for x in (profile["city"], profile["region"], profile["country"]) if x) + ". Do not infer an exact address or claim the user is currently there.")
            bits.append("Use Indian context where relevant: INR when appropriate, Indian date/number conventions, local education/civic context, and culturally aware examples. Avoid stereotypes and ask if a regional assumption matters.")
            bits.append("User language preference: " + chosen + ("; secondary: " + ", ".join(profile["secondary_languages"]) if profile["secondary_languages"] else "") + ". Follow the user's current message if it clearly requests another language.")
            bits.append("Timezone preference: " + profile["timezone"] + ". Use only for local-time interpretation; verify current time when needed.")
        else:
            bits.append("Location personalization is disabled. Do not infer or use device location. Use Indian context only when the user's message makes it relevant.")
            if detected != "english": bits.append("Current message language signal: " + detected + ". Reply naturally in the same language/register unless asked otherwise.")
        bits.append("Never invent live weather, traffic, opening hours, local events, prices, or location-specific facts; verify with live sources when required.")
        return "\n".join(bits)

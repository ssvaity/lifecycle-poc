"""Small on-disk JSON cache (SQLite) so repeat lookups cost no API credits."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = Path(os.getenv("LIFECYCLE_CACHE", ROOT / ".cache" / "lifecycle.sqlite"))

DAY = 24 * 3600


def _connect() -> sqlite3.Connection:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(PATH)
    db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, saved REAL, value TEXT)")
    return db


def get(key: str, max_age_s: float) -> tuple[object, float] | None:
    """(value, saved_at) if the key was saved less than max_age_s ago."""
    with _connect() as db:
        row = db.execute("SELECT value, saved FROM cache WHERE key = ?", (key,)).fetchone()
    if row is None or time.time() - row[1] > max_age_s:
        return None
    return json.loads(row[0]), row[1]


def put(key: str, value: object) -> None:
    with _connect() as db:
        db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (key, time.time(), json.dumps(value)))


def clear() -> int:
    """Delete everything; returns how many entries were removed."""
    with _connect() as db:
        return db.execute("DELETE FROM cache").rowcount

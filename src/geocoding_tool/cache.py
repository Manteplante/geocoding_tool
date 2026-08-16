"""On-disk cache of geocoding results.

Re-running the same input file costs zero provider calls. This is the single
biggest lever on Google spend, so it is on by default.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from geocoding_tool.config import cache_path

_WHITESPACE = re.compile(r"\s+")

# Every statement below binds its values with ``?`` placeholders. Query strings
# and provider names are user data and must never be interpolated into SQL --
# see the injection tests in tests/test_cache.py. _SCHEMA in particular must
# stay a static literal: executescript() runs multiple statements, so a single
# formatted value there would be a straight path to arbitrary SQL execution.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS geocode_cache (
    provider   TEXT NOT NULL,
    query_key  TEXT NOT NULL,
    query      TEXT NOT NULL,
    latitude   REAL,
    longitude  REAL,
    address    TEXT,
    raw        TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (provider, query_key)
);
"""


def normalize_query(query: str) -> str:
    """Casefold and collapse whitespace so trivial variants share a hit."""
    return _WHITESPACE.sub(" ", query.strip()).casefold()


class GeocodeCache:
    """SQLite-backed cache. Pass ``":memory:"`` for a throwaway one."""

    def __init__(self, path: str | Path | None = None, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.hits = 0
        self.path = Path(path) if path is not None else cache_path()
        self._conn: sqlite3.Connection | None = None
        if self.enabled:
            self._connect()

    def _connect(self) -> None:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def get(self, provider: str, query: str):
        """Return a cached :class:`GeocodeResult`, or ``None`` on a miss."""
        from geocoding_tool.base import GeocodeResult

        if not self.enabled or self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT query, latitude, longitude, address, raw "
            "FROM geocode_cache WHERE provider = ? AND query_key = ?",
            (provider, normalize_query(query)),
        ).fetchone()
        if row is None:
            return None
        self.hits += 1
        return GeocodeResult(
            query=query,
            provider=provider,
            latitude=row[1],
            longitude=row[2],
            address=row[3],
            raw=json.loads(row[4]) if row[4] else None,
        )

    def set(self, result) -> None:
        """Store a successful result. Failures are never cached."""
        if not self.enabled or self._conn is None or result.error is not None:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO geocode_cache "
            "(provider, query_key, query, latitude, longitude, address, raw) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.provider,
                normalize_query(result.query),
                result.query,
                result.latitude,
                result.longitude,
                result.address,
                json.dumps(result.raw) if result.raw is not None else None,
            ),
        )
        self._conn.commit()

    def __len__(self) -> int:
        if not self.enabled or self._conn is None:
            return 0
        return self._conn.execute("SELECT COUNT(*) FROM geocode_cache").fetchone()[0]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

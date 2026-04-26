"""
cache/storage/cache_db.py
─────────────────────────
SQLite-backed persistence layer for the Distributed Cache.

Responsibilities
────────────────
• Write-through: every put() lands in both the in-memory LRU and SQLite.
• Warm-up: on node startup, load_from_db() replays unexpired rows back
  into the LRU so a node restart doesn't cold-start the cache.
• Update: update_scan_result() lets a worker overwrite a stale result
  (e.g. after a re-scan) and bumps updated_at + resets TTL.
• Eviction sync: when LRU evicts an entry it calls db.delete() so the
  DB doesn't grow unbounded.

Schema
──────
CREATE TABLE cache_entries (
    layer_hash   TEXT PRIMARY KEY,
    scan_result  TEXT NOT NULL,          -- JSON blob
    created_at   REAL NOT NULL,          -- Unix timestamp
    updated_at   REAL NOT NULL,
    expires_at   REAL NOT NULL,
    hit_count    INTEGER DEFAULT 0
);
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from shared.utils.logger import get_logger

logger = get_logger("cache.cache_db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cache_entries (
    layer_hash   TEXT PRIMARY KEY,
    scan_result  TEXT    NOT NULL,
    created_at   REAL    NOT NULL,
    updated_at   REAL    NOT NULL,
    expires_at   REAL    NOT NULL,
    hit_count    INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_expires_at ON cache_entries (expires_at);
"""


class CacheDB:
    """Thread-safe SQLite persistence for scan-result cache entries."""

    def __init__(self, db_path: str = "cache_store.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"CacheDB initialised at '{db_path}'")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            with self._connect() as conn:
                conn.execute(_CREATE_TABLE)
                conn.execute(_CREATE_INDEX)
                conn.commit()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def put(self, layer_hash: str, scan_result: dict, ttl_seconds: int = 3600) -> None:
        """Insert or replace an entry.  Called by LayerScanCache.put()."""
        now = time.time()
        payload = json.dumps(scan_result)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO cache_entries
                        (layer_hash, scan_result, created_at, updated_at, expires_at, hit_count)
                    VALUES (?, ?, ?, ?, ?, 0)
                    ON CONFLICT(layer_hash) DO UPDATE SET
                        scan_result = excluded.scan_result,
                        updated_at  = excluded.updated_at,
                        expires_at  = excluded.expires_at
                    """,
                    (layer_hash, payload, now, now, now + ttl_seconds),
                )
                conn.commit()

    def get(self, layer_hash: str) -> Optional[dict]:
        """Return the scan_result dict if the row exists and has not expired."""
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT scan_result, expires_at FROM cache_entries WHERE layer_hash = ?",
                    (layer_hash,),
                ).fetchone()

        if row is None:
            return None
        if now > row["expires_at"]:
            self.delete(layer_hash)
            return None

        self.increment_hit_count(layer_hash)
        return json.loads(row["scan_result"])

    def update(self, layer_hash: str, scan_result: dict, ttl_seconds: int = 3600) -> bool:
        """
        Overwrite the scan_result for an existing entry and reset its TTL.
        Returns True if a row was updated, False if the key was not found.
        Used when a worker re-scans a layer and gets a fresher report.
        """
        now = time.time()
        payload = json.dumps(scan_result)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE cache_entries
                    SET scan_result = ?,
                        updated_at  = ?,
                        expires_at  = ?
                    WHERE layer_hash = ?
                    """,
                    (payload, now, now + ttl_seconds, layer_hash),
                )
                conn.commit()
                return cursor.rowcount > 0

    def delete(self, layer_hash: str) -> None:
        """Remove a single entry (called on TTL expiry or explicit invalidation)."""
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM cache_entries WHERE layer_hash = ?", (layer_hash,)
                )
                conn.commit()

    def increment_hit_count(self, layer_hash: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE cache_entries SET hit_count = hit_count + 1 WHERE layer_hash = ?",
                    (layer_hash,),
                )
                conn.commit()

    def purge_expired(self) -> int:
        """Delete all expired rows.  Call periodically from a background thread."""
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE expires_at < ?", (now,)
                )
                conn.commit()
                deleted = cursor.rowcount
        if deleted:
            logger.info(f"Purged {deleted} expired cache entries from DB")
        return deleted

    def load_all_valid(self) -> list[dict]:
        """
        Return all unexpired rows for LRU warm-up on node restart.
        Each dict has keys: layer_hash, scan_result, expires_at, hit_count.
        """
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT layer_hash, scan_result, expires_at, hit_count
                    FROM cache_entries
                    WHERE expires_at > ?
                    ORDER BY expires_at ASC
                    """,
                    (now,),
                ).fetchall()

        return [
            {
                "layer_hash": r["layer_hash"],
                "scan_result": json.loads(r["scan_result"]),
                "expires_at": r["expires_at"],
                "hit_count": r["hit_count"],
            }
            for r in rows
        ]

    def stats(self) -> dict:
        """Aggregate statistics straight from the DB."""
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM cache_entries"
                ).fetchone()[0]
                active = conn.execute(
                    "SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?", (now,)
                ).fetchone()[0]
                total_hits = conn.execute(
                    "SELECT COALESCE(SUM(hit_count), 0) FROM cache_entries"
                ).fetchone()[0]
        return {
            "db_total_entries": total,
            "db_active_entries": active,
            "db_expired_entries": total - active,
            "db_total_hits": total_hits,
        }
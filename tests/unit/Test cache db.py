"""
tests/unit/test_cache_db.py
────────────────────────────
Unit tests for:
  • CacheDB  (cache/storage/cache_db.py)
  • LayerScanCache with DB integration (cache/cache_common.py)

Run with:  pytest tests/unit/test_cache_db.py -v
"""

import time
import pytest

from cache.storage.cache_db import CacheDB
from cache.cache_common import LayerScanCache


# ─────────────────────────────────────────────────────────────────────── #
#  Fixtures                                                               #
# ─────────────────────────────────────────────────────────────────────── #

@pytest.fixture
def tmp_db(tmp_path):
    """Fresh CacheDB backed by a temp file for each test."""
    return CacheDB(db_path=str(tmp_path / "test_cache.db"))


@pytest.fixture
def cache_with_db(tmp_db):
    """LayerScanCache wired to a temp CacheDB."""
    return LayerScanCache(capacity=10, ttl_seconds=60, db=tmp_db)


SAMPLE_RESULT = {"scanner": "trivy", "critical": 1, "high": 2, "status": "completed"}


# ─────────────────────────────────────────────────────────────────────── #
#  CacheDB unit tests                                                     #
# ─────────────────────────────────────────────────────────────────────── #

class TestCacheDB:

    def test_put_and_get(self, tmp_db):
        tmp_db.put("hash1", SAMPLE_RESULT)
        result = tmp_db.get("hash1")
        assert result is not None
        assert result["critical"] == 1

    def test_get_missing_returns_none(self, tmp_db):
        assert tmp_db.get("nonexistent") is None

    def test_get_expired_returns_none(self, tmp_db):
        tmp_db.put("hash_exp", SAMPLE_RESULT, ttl_seconds=0)
        time.sleep(0.05)
        assert tmp_db.get("hash_exp") is None

    def test_update_existing(self, tmp_db):
        tmp_db.put("hash2", SAMPLE_RESULT)
        updated = {"scanner": "trivy", "critical": 0, "status": "clean"}
        ok = tmp_db.update("hash2", updated)
        assert ok is True
        result = tmp_db.get("hash2")
        assert result["critical"] == 0

    def test_update_nonexistent_returns_false(self, tmp_db):
        ok = tmp_db.update("ghost_hash", SAMPLE_RESULT)
        assert ok is False

    def test_delete(self, tmp_db):
        tmp_db.put("hash3", SAMPLE_RESULT)
        tmp_db.delete("hash3")
        assert tmp_db.get("hash3") is None

    def test_purge_expired(self, tmp_db):
        tmp_db.put("alive", SAMPLE_RESULT, ttl_seconds=3600)
        tmp_db.put("dead",  SAMPLE_RESULT, ttl_seconds=0)
        time.sleep(0.05)
        removed = tmp_db.purge_expired()
        assert removed >= 1
        assert tmp_db.get("alive") is not None
        assert tmp_db.get("dead") is None

    def test_load_all_valid_excludes_expired(self, tmp_db):
        tmp_db.put("v1", SAMPLE_RESULT, ttl_seconds=3600)
        tmp_db.put("v2", SAMPLE_RESULT, ttl_seconds=0)
        time.sleep(0.05)
        rows = tmp_db.load_all_valid()
        hashes = [r["layer_hash"] for r in rows]
        assert "v1" in hashes
        assert "v2" not in hashes

    def test_stats(self, tmp_db):
        tmp_db.put("s1", SAMPLE_RESULT)
        s = tmp_db.stats()
        assert s["db_total_entries"] == 1
        assert s["db_active_entries"] == 1

    def test_hit_count_increments(self, tmp_db):
        tmp_db.put("h1", SAMPLE_RESULT)
        tmp_db.get("h1")
        tmp_db.get("h1")
        rows = tmp_db.load_all_valid()
        row = next(r for r in rows if r["layer_hash"] == "h1")
        assert row["hit_count"] == 2


# ─────────────────────────────────────────────────────────────────────── #
#  LayerScanCache + DB integration tests                                  #
# ─────────────────────────────────────────────────────────────────────── #

class TestLayerScanCacheWithDB:

    def test_put_persists_to_db(self, cache_with_db, tmp_db):
        cache_with_db.put("lh1", SAMPLE_RESULT)
        assert tmp_db.get("lh1") is not None

    def test_get_hits_lru_first(self, cache_with_db):
        cache_with_db.put("lh2", SAMPLE_RESULT)
        result = cache_with_db.get("lh2")
        assert result is not None
        stats = cache_with_db.stats()
        assert stats["lru_hits"] >= 1

    def test_get_falls_back_to_db(self, tmp_db):
        # Seed DB directly, bypass LRU
        tmp_db.put("lh3", SAMPLE_RESULT)
        fresh_cache = LayerScanCache(capacity=10, ttl_seconds=60, db=tmp_db)
        # Remove from LRU without touching DB
        fresh_cache.lru.delete("lh3")
        result = fresh_cache.get("lh3")
        assert result is not None
        assert fresh_cache.stats()["db_hits"] >= 1

    def test_warm_from_db_on_restart(self, tmp_db):
        # Simulate node that persisted entries, then restarted
        tmp_db.put("lh4", SAMPLE_RESULT, ttl_seconds=3600)
        restarted_cache = LayerScanCache(capacity=10, ttl_seconds=3600, db=tmp_db)
        assert restarted_cache.lru.size() >= 1

    def test_update_existing_entry(self, cache_with_db):
        cache_with_db.put("lh5", SAMPLE_RESULT)
        ok = cache_with_db.update("lh5", {"critical": 0, "status": "clean"})
        assert ok is True
        result = cache_with_db.get("lh5")
        assert result["critical"] == 0

    def test_update_nonexistent_returns_false(self, cache_with_db):
        assert cache_with_db.update("ghost", SAMPLE_RESULT) is False

    def test_invalidate_removes_from_both_layers(self, cache_with_db, tmp_db):
        cache_with_db.put("lh6", SAMPLE_RESULT)
        cache_with_db.invalidate("lh6")
        assert cache_with_db.lru.get("lh6") is None
        assert tmp_db.get("lh6") is None

    def test_stats_include_db_fields(self, cache_with_db):
        cache_with_db.put("lh7", SAMPLE_RESULT)
        cache_with_db.get("lh7")
        s = cache_with_db.stats()
        assert "db_total_entries" in s
        assert "hit_ratio" in s
        assert s["hits"] >= 1

    def test_memory_only_mode(self):
        """LayerScanCache without a DB should still work fine."""
        c = LayerScanCache(capacity=5, ttl_seconds=60, db=None)
        c.put("m1", SAMPLE_RESULT)
        assert c.get("m1") is not None
        assert c.update("m1", {"critical": 0}) is True
        c.invalidate("m1")
        assert c.get("m1") is None
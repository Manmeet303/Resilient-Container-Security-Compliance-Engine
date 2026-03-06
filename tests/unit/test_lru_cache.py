from cache.storage.lru_cache import LRUCache

def test_set_and_get():
    c = LRUCache(max_size=10)
    c.set("k1", {"report": "data"})
    assert c.get("k1")["report"] == "data"

def test_miss_returns_none():
    assert LRUCache().get("missing") is None

def test_eviction():
    c = LRUCache(max_size=3)
    for i in range(1, 5):
        c.set(f"k{i}", {"v": i})
    assert c.get("k1") is None
    assert c.get("k4") is not None

def test_hit_ratio():
    c = LRUCache()
    c.set("k1", {"v": 1})
    c.get("k1"); c.get("missing")
    assert c.hit_ratio() == 0.5

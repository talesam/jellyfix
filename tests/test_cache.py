"""Tests for utils/cache.py — file caching with expiration."""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "usr" / "share"))

from jellyfix.utils.cache import CacheManager


@pytest.fixture
def cache(tmp_path):
    return CacheManager(cache_dir=tmp_path, expiration_days=30)


class TestSaveAndGet:
    def test_save_returns_path(self, cache):
        path = cache.save("k1", b"hello", ext="txt")
        assert path.exists()
        assert path.read_bytes() == b"hello"

    def test_get_returns_path(self, cache):
        cache.save("k1", b"hello", ext="txt")
        result = cache.get("k1")
        assert result is not None
        assert Path(result).read_bytes() == b"hello"

    def test_get_missing_key(self, cache):
        assert cache.get("never-set") is None

    def test_exists(self, cache):
        cache.save("k1", b"x")
        assert cache.exists("k1") is True
        assert cache.exists("never-set") is False

    def test_save_overwrites_index_entry(self, cache):
        cache.save("k1", b"first")
        cache.save("k1", b"second")
        assert Path(cache.get("k1")).read_bytes() == b"second"


class TestExpiration:
    def test_expired_entry_purged_on_get(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path, expiration_days=30)
        cache.save("k1", b"x")
        # Rewrite the index timestamp to 60 days ago.
        cache.index["k1"]["timestamp"] = (datetime.now() - timedelta(days=60)).isoformat()
        cache._save_index()

        assert cache.get("k1") is None
        assert "k1" not in cache.index

    def test_cleanup_expired_at_init(self, tmp_path):
        c1 = CacheManager(cache_dir=tmp_path, expiration_days=30)
        c1.save("k1", b"x")
        c1.index["k1"]["timestamp"] = (datetime.now() - timedelta(days=60)).isoformat()
        c1._save_index()

        # Fresh instance triggers cleanup
        c2 = CacheManager(cache_dir=tmp_path, expiration_days=30)
        assert "k1" not in c2.index


class TestClearOperations:
    def test_clear_all(self, cache):
        cache.save("k1", b"a")
        cache.save("k2", b"b")
        cache.clear_all()
        assert cache.get("k1") is None
        assert cache.get("k2") is None
        assert cache.index == {}

    def test_get_removes_orphan_file_reference(self, cache):
        cache.save("k1", b"x")
        # Delete the underlying file but leave the index entry
        Path(cache.index["k1"]["path"]).unlink()
        assert cache.get("k1") is None
        assert "k1" not in cache.index


class TestStats:
    def test_empty_stats(self, cache):
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 0
        assert stats["total_size"] == 0
        assert stats["oldest_entry"] is None

    def test_size_accumulates(self, cache):
        cache.save("k1", b"x" * 100)
        cache.save("k2", b"y" * 200)
        assert cache.get_cache_size() == 300

    def test_stats_with_entries(self, cache):
        cache.save("k1", b"hello")
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 1
        assert stats["total_size"] == 5
        assert stats["oldest_entry"] is not None


class TestCorruptedIndex:
    def test_corrupted_index_starts_fresh(self, tmp_path):
        (tmp_path / "index.json").write_text("{ not valid json")
        cache = CacheManager(cache_dir=tmp_path, expiration_days=30)
        assert cache.index == {}

    def test_index_with_invalid_timestamp_is_dropped(self, tmp_path):
        index_path = tmp_path / "index.json"
        index_path.write_text(json.dumps({
            "bad": {"path": str(tmp_path / "x.dat"), "timestamp": "not-a-date", "size": 0}
        }))
        cache = CacheManager(cache_dir=tmp_path, expiration_days=30)
        # Invalid timestamp entries are pruned by _cleanup_expired
        assert "bad" not in cache.index

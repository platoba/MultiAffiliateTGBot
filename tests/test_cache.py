"""Tests for link cache."""

import time
import pytest
from app.services.cache import LinkCache


class TestLinkCache:
    def test_put_and_get(self, tmp_cache):
        tmp_cache.put("https://amazon.com/dp/B123", "amazon", "https://amazon.com/dp/B123?tag=t")
        result = tmp_cache.get("https://amazon.com/dp/B123")
        assert result is not None
        assert result["platform"] == "amazon"
        assert result["affiliate_url"] == "https://amazon.com/dp/B123?tag=t"

    def test_get_missing(self, tmp_cache):
        assert tmp_cache.get("https://nonexistent.com") is None

    def test_ttl_expiry(self, tmp_path):
        cache = LinkCache(str(tmp_path / "cache.db"), ttl_hours=0)  # 0 hour TTL = immediate expiry
        cache.put("https://amazon.com/dp/B123", "amazon", "aff_url")
        time.sleep(0.1)
        assert cache.get("https://amazon.com/dp/B123") is None
        cache.close()

    def test_case_insensitive(self, tmp_cache):
        tmp_cache.put("https://AMAZON.COM/dp/B123", "amazon", "aff")
        result = tmp_cache.get("https://amazon.com/dp/B123")
        assert result is not None

    def test_overwrite(self, tmp_cache):
        tmp_cache.put("https://amazon.com/dp/B123", "amazon", "aff1")
        tmp_cache.put("https://amazon.com/dp/B123", "amazon", "aff2")
        result = tmp_cache.get("https://amazon.com/dp/B123")
        assert result["affiliate_url"] == "aff2"

    def test_size(self, tmp_cache):
        assert tmp_cache.size() == 0
        tmp_cache.put("url1", "amazon", "aff1")
        tmp_cache.put("url2", "shopee", "aff2")
        assert tmp_cache.size() == 2

    def test_cleanup(self, tmp_path):
        cache = LinkCache(str(tmp_path / "cache.db"), ttl_hours=0)
        cache.put("url1", "amazon", "aff1")
        time.sleep(0.1)
        deleted = cache.cleanup()
        assert deleted >= 1
        assert cache.size() == 0
        cache.close()

    def test_product_id_stored(self, tmp_cache):
        tmp_cache.put("url", "amazon", "aff", product_id="B123")
        result = tmp_cache.get("url")
        assert result["product_id"] == "B123"

    def test_url_whitespace_trimmed(self, tmp_cache):
        tmp_cache.put("  https://amazon.com/dp/B123  ", "amazon", "aff")
        result = tmp_cache.get("https://amazon.com/dp/B123")
        assert result is not None

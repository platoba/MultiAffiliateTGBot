"""Tests for analytics module."""

import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use temp dir for test data
_tmpdir = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _tmpdir

from analytics import record_conversion, get_stats_summary, get_user_stats, _load_stats, STATS_FILE


class TestAnalytics:
    def setup_method(self):
        """Clean stats before each test."""
        if STATS_FILE.exists():
            STATS_FILE.unlink()

    def test_record_conversion(self):
        record_conversion("amazon", 123, "TestUser", "https://amazon.com/dp/B123", "https://amazon.com/dp/B123?tag=test")
        stats = _load_stats()
        assert stats["total"] == 1
        assert stats["by_platform"]["amazon"] == 1
        assert "123" in stats["by_user"]

    def test_multiple_platforms(self):
        record_conversion("amazon", 1, "User1", "url1", "aff1")
        record_conversion("shopee", 2, "User2", "url2", "aff2")
        record_conversion("amazon", 1, "User1", "url3", "aff3")
        stats = _load_stats()
        assert stats["total"] == 3
        assert stats["by_platform"]["amazon"] == 2
        assert stats["by_platform"]["shopee"] == 1

    def test_stats_summary_empty(self):
        result = get_stats_summary()
        assert "暂无" in result

    def test_stats_summary_with_data(self):
        record_conversion("amazon", 1, "User1", "url1", "aff1")
        result = get_stats_summary()
        assert "总计: 1" in result
        assert "amazon" in result

    def test_user_stats_empty(self):
        result = get_user_stats(999)
        assert "还没有" in result

    def test_user_stats_with_data(self):
        record_conversion("amazon", 42, "TestUser", "url", "aff")
        result = get_user_stats(42)
        assert "总转换: 1" in result

    def test_daily_tracking(self):
        record_conversion("amazon", 1, "User", "url", "aff")
        stats = _load_stats()
        assert len(stats["daily"]) == 1

    def test_link_history_cap(self):
        """Links should be capped at 1000."""
        for i in range(1005):
            record_conversion("amazon", 1, "User", f"url{i}", f"aff{i}")
        stats = _load_stats()
        assert len(stats["links"]) == 1000

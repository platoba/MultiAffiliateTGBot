"""Tests for database service."""

import pytest
from app.services.database import Database


class TestDatabase:
    def test_record_conversion(self, tmp_db):
        tmp_db.record_conversion(
            "amazon", 123, "TestUser", 0, "",
            "https://amazon.com/dp/B123", "https://amazon.com/dp/B123?tag=t"
        )
        stats = tmp_db.get_total_stats()
        assert stats["total"] == 1
        assert stats["by_platform"]["amazon"] == 1

    def test_multiple_conversions(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User1", 0, "", "url1", "aff1")
        tmp_db.record_conversion("shopee", 2, "User2", 0, "", "url2", "aff2")
        tmp_db.record_conversion("amazon", 1, "User1", 0, "", "url3", "aff3")
        stats = tmp_db.get_total_stats()
        assert stats["total"] == 3
        assert stats["by_platform"]["amazon"] == 2
        assert stats["by_platform"]["shopee"] == 1

    def test_today_count(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url", "aff")
        stats = tmp_db.get_total_stats()
        assert stats["today"] >= 1

    def test_week_count(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url", "aff")
        stats = tmp_db.get_total_stats()
        assert stats["this_week"] >= 1

    def test_top_users(self, tmp_db):
        for i in range(5):
            tmp_db.record_conversion("amazon", 1, "PowerUser", 0, "", f"url{i}", f"aff{i}")
        tmp_db.record_conversion("shopee", 2, "Casual", 0, "", "url", "aff")
        top = tmp_db.get_top_users(10)
        assert len(top) == 2
        assert top[0]["username"] == "PowerUser"
        assert top[0]["total_conversions"] == 5

    def test_user_stats(self, tmp_db):
        tmp_db.record_conversion("amazon", 42, "TestUser", 0, "", "url", "aff")
        tmp_db.record_conversion("shopee", 42, "TestUser", 0, "", "url2", "aff2")
        stats = tmp_db.get_user_stats(42)
        assert stats is not None
        assert stats["total_conversions"] == 2
        assert "amazon" in stats["by_platform"]
        assert "shopee" in stats["by_platform"]

    def test_user_stats_nonexistent(self, tmp_db):
        assert tmp_db.get_user_stats(999) is None

    def test_daily_stats(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url", "aff")
        daily = tmp_db.get_daily_stats(7)
        assert len(daily) >= 1

    def test_group_tracking(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", -100, "TestGroup", "url", "aff")
        groups = tmp_db.get_group_stats()
        assert len(groups) == 1
        assert groups[0]["chat_title"] == "TestGroup"

    def test_recent_conversions(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url1", "aff1")
        tmp_db.record_conversion("shopee", 1, "User", 0, "", "url2", "aff2")
        recent = tmp_db.get_recent_conversions(10)
        assert len(recent) == 2
        assert recent[0]["platform"] == "shopee"  # Most recent first

    def test_block_user(self, tmp_db):
        tmp_db.record_conversion("amazon", 42, "User", 0, "", "url", "aff")
        assert not tmp_db.is_user_blocked(42)
        tmp_db.block_user(42)
        assert tmp_db.is_user_blocked(42)
        tmp_db.unblock_user(42)
        assert not tmp_db.is_user_blocked(42)

    def test_block_nonexistent_user(self, tmp_db):
        assert not tmp_db.is_user_blocked(999)

    def test_group_enabled(self, tmp_db):
        assert tmp_db.is_group_enabled(-100)  # Default enabled
        tmp_db.set_group_enabled(-100, False)
        assert not tmp_db.is_group_enabled(-100)
        tmp_db.set_group_enabled(-100, True)
        assert tmp_db.is_group_enabled(-100)

    def test_export_conversions(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url1", "aff1")
        tmp_db.record_conversion("shopee", 2, "User2", 0, "", "url2", "aff2")
        data = tmp_db.export_conversions(30)
        assert len(data) == 2
        assert all("platform" in d for d in data)

    def test_blocked_users_excluded_from_top(self, tmp_db):
        for i in range(5):
            tmp_db.record_conversion("amazon", 1, "Spammer", 0, "", f"url{i}", f"aff{i}")
        tmp_db.record_conversion("amazon", 2, "Good", 0, "", "url", "aff")
        tmp_db.block_user(1)
        top = tmp_db.get_top_users(10)
        assert top[0]["username"] == "Good"

    def test_product_id_stored(self, tmp_db):
        tmp_db.record_conversion("amazon", 1, "User", 0, "", "url", "aff", product_id="B123")
        recent = tmp_db.get_recent_conversions(1)
        assert recent[0]["product_id"] == "B123"

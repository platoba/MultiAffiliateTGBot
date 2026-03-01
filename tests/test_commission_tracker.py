"""Tests for commission tracker."""

import os
import pytest
import tempfile
from app.services.commission_tracker import (
    CommissionTracker,
    CommissionRate,
    CommissionTier,
    EarningsReport,
    Goal,
    DEFAULT_RATES,
    AMAZON_CATEGORY_RATES,
    PayoutStatus,
)


@pytest.fixture
def tracker(tmp_path):
    db = str(tmp_path / "commissions.db")
    t = CommissionTracker(db_path=db)
    yield t
    t.close()


@pytest.fixture
def tracker_with_data(tracker):
    """Tracker pre-populated with test data."""
    # Record some clicks and commissions
    for i in range(20):
        tracker.record_click("amazon", user_id=1001, product_id=f"ASIN{i % 5}")
    for i in range(10):
        tracker.record_click("shopee", user_id=1002, product_id=f"SH{i}")

    # Record commissions
    tracker.record_commission("amazon", 1001, 50.0, product_id="ASIN0", category="electronics")
    tracker.record_commission("amazon", 1001, 120.0, product_id="ASIN1", category="fashion")
    tracker.record_commission("amazon", 1001, 30.0, product_id="ASIN2")
    tracker.record_commission("shopee", 1002, 25.0, product_id="SH0")
    tracker.record_commission("shopee", 1002, 45.0, product_id="SH1")
    return tracker


class TestCommissionRate:
    def test_effective_rate(self):
        r = CommissionRate("amazon", base_rate=0.04, bonus_rate=0.01)
        assert r.effective_rate == 0.05

    def test_estimate_earnings(self):
        r = CommissionRate("amazon", base_rate=0.04)
        assert r.estimate_earnings(100.0) == 4.0

    def test_estimate_earnings_with_bonus(self):
        r = CommissionRate("amazon", base_rate=0.04, bonus_rate=0.02)
        assert r.estimate_earnings(100.0) == 6.0

    def test_default_min_payout(self):
        r = CommissionRate("test", base_rate=0.05)
        assert r.min_payout == 10.0

    def test_default_cookie_days(self):
        r = CommissionRate("test", base_rate=0.05)
        assert r.cookie_days == 30


class TestGoal:
    def test_progress(self):
        g = Goal(goal_id="g1", target_amount=100.0, current_amount=50.0)
        assert g.progress == 50.0

    def test_progress_exceeded(self):
        g = Goal(goal_id="g1", target_amount=100.0, current_amount=150.0)
        assert g.progress == 100.0

    def test_progress_zero_target(self):
        g = Goal(goal_id="g1", target_amount=0.0)
        assert g.progress == 0.0

    def test_is_achieved(self):
        assert Goal(goal_id="g1", target_amount=100.0, current_amount=100.0).is_achieved
        assert Goal(goal_id="g1", target_amount=100.0, current_amount=150.0).is_achieved
        assert not Goal(goal_id="g1", target_amount=100.0, current_amount=99.0).is_achieved

    def test_remaining(self):
        g = Goal(goal_id="g1", target_amount=100.0, current_amount=60.0)
        assert g.remaining == 40.0

    def test_remaining_exceeded(self):
        g = Goal(goal_id="g1", target_amount=100.0, current_amount=150.0)
        assert g.remaining == 0


class TestDefaultRates:
    def test_all_platforms_have_rates(self):
        for p in ["amazon", "shopee", "lazada", "aliexpress", "tiktok"]:
            assert p in DEFAULT_RATES

    def test_amazon_rate(self):
        assert DEFAULT_RATES["amazon"].base_rate == 0.04

    def test_shopee_rate(self):
        assert DEFAULT_RATES["shopee"].base_rate == 0.06

    def test_amazon_categories(self):
        assert "luxury_beauty" in AMAZON_CATEGORY_RATES
        assert "electronics" in AMAZON_CATEGORY_RATES
        assert AMAZON_CATEGORY_RATES["luxury_beauty"] == 0.10
        assert AMAZON_CATEGORY_RATES["electronics"] == 0.03


class TestCommissionTracker:
    def test_init(self, tracker):
        assert tracker.conn is not None

    def test_set_custom_rate(self, tracker):
        custom = CommissionRate("amazon", base_rate=0.08, bonus_rate=0.02)
        tracker.set_rate("amazon", custom)
        rate = tracker.get_rate("amazon")
        assert rate.base_rate == 0.08
        assert rate.bonus_rate == 0.02

    def test_get_rate_default(self, tracker):
        rate = tracker.get_rate("amazon")
        assert rate.base_rate == 0.04

    def test_get_rate_unknown_platform(self, tracker):
        rate = tracker.get_rate("unknown_platform")
        assert rate.base_rate == 0.04  # Default fallback

    def test_get_rate_amazon_category(self, tracker):
        rate = tracker.get_rate("amazon", category="luxury_beauty")
        assert rate.base_rate == 0.10

    def test_get_rate_amazon_default_category(self, tracker):
        rate = tracker.get_rate("amazon", category="nonexistent")
        assert rate.base_rate == 0.04  # Falls back to default

    def test_record_click(self, tracker):
        tracker.record_click("amazon", 1001, "B08N5WRWNW", "track123")
        row = tracker.conn.execute("SELECT COUNT(*) as cnt FROM clicks").fetchone()
        assert row["cnt"] == 1

    def test_record_multiple_clicks(self, tracker):
        for i in range(5):
            tracker.record_click("amazon", 1001)
        row = tracker.conn.execute("SELECT COUNT(*) as cnt FROM clicks").fetchone()
        assert row["cnt"] == 5

    def test_record_commission(self, tracker):
        commission = tracker.record_commission("amazon", 1001, 100.0)
        assert commission == 4.0  # 4% of 100

    def test_record_commission_with_category(self, tracker):
        commission = tracker.record_commission(
            "amazon", 1001, 100.0, category="luxury_beauty"
        )
        assert commission == 10.0  # 10% of 100

    def test_record_commission_shopee(self, tracker):
        commission = tracker.record_commission("shopee", 1001, 50.0)
        assert commission == 3.0  # 6% of 50

    def test_commission_stored_in_db(self, tracker):
        tracker.record_commission("amazon", 1001, 100.0)
        row = tracker.conn.execute(
            "SELECT * FROM commissions WHERE user_id = 1001"
        ).fetchone()
        assert row is not None
        assert row["sale_amount"] == 100.0
        assert row["commission_amount"] == 4.0

    def test_record_commission_with_order(self, tracker):
        tracker.record_commission(
            "amazon", 1001, 100.0,
            product_id="B123", order_id="ORD-001", click_id="CLK-001"
        )
        row = tracker.conn.execute(
            "SELECT * FROM commissions WHERE order_id = 'ORD-001'"
        ).fetchone()
        assert row["product_id"] == "B123"
        assert row["click_id"] == "CLK-001"


class TestEarnings:
    def test_get_earnings_basic(self, tracker_with_data):
        earnings = tracker_with_data.get_earnings(days=30)
        assert earnings["total_conversions"] == 5
        assert earnings["total_clicks"] == 30
        assert earnings["total_sales"] > 0
        assert earnings["total_commission"] > 0

    def test_get_earnings_by_platform(self, tracker_with_data):
        earnings = tracker_with_data.get_earnings(platform="amazon", days=30)
        assert earnings["total_conversions"] == 3

    def test_get_earnings_by_user(self, tracker_with_data):
        earnings = tracker_with_data.get_earnings(user_id=1001, days=30)
        assert earnings["total_conversions"] == 3

    def test_get_earnings_empty(self, tracker):
        earnings = tracker.get_earnings(days=30)
        assert earnings["total_conversions"] == 0
        assert earnings["total_commission"] == 0.0

    def test_conversion_rate_calculation(self, tracker_with_data):
        earnings = tracker_with_data.get_earnings(days=30)
        assert earnings["conversion_rate"] > 0

    def test_avg_order_value(self, tracker_with_data):
        earnings = tracker_with_data.get_earnings(days=30)
        assert earnings["avg_order_value"] > 0


class TestPlatformBreakdown:
    def test_breakdown(self, tracker_with_data):
        breakdown = tracker_with_data.get_platform_breakdown(days=30)
        assert len(breakdown) == 2
        platforms = {b["platform"] for b in breakdown}
        assert "amazon" in platforms
        assert "shopee" in platforms

    def test_breakdown_sorted_by_commission(self, tracker_with_data):
        breakdown = tracker_with_data.get_platform_breakdown(days=30)
        commissions = [b["commission"] for b in breakdown]
        assert commissions == sorted(commissions, reverse=True)

    def test_breakdown_empty(self, tracker):
        assert tracker.get_platform_breakdown(days=30) == []


class TestTopProducts:
    def test_top_products(self, tracker_with_data):
        top = tracker_with_data.get_top_products(days=30, limit=5)
        assert len(top) > 0
        assert "product_id" in top[0]
        assert "total_commission" in top[0]

    def test_top_products_sorted(self, tracker_with_data):
        top = tracker_with_data.get_top_products(days=30)
        commissions = [p["total_commission"] for p in top]
        assert commissions == sorted(commissions, reverse=True)

    def test_top_products_empty(self, tracker):
        assert tracker.get_top_products(days=30) == []


class TestLeaderboard:
    def test_user_leaderboard(self, tracker_with_data):
        lb = tracker_with_data.get_user_leaderboard(days=30)
        assert len(lb) == 2
        assert lb[0]["user_id"] in [1001, 1002]

    def test_leaderboard_sorted(self, tracker_with_data):
        lb = tracker_with_data.get_user_leaderboard(days=30)
        commissions = [u["total_commission"] for u in lb]
        assert commissions == sorted(commissions, reverse=True)


class TestDailyTrend:
    def test_daily_trend(self, tracker_with_data):
        trend = tracker_with_data.get_daily_trend(days=30)
        assert len(trend) > 0
        assert "date" in trend[0]
        assert "commission" in trend[0]

    def test_daily_trend_by_platform(self, tracker_with_data):
        trend = tracker_with_data.get_daily_trend(days=30, platform="amazon")
        assert len(trend) > 0


class TestPayoutEstimation:
    def test_estimate_payout(self, tracker_with_data):
        payout = tracker_with_data.estimate_payout(days=30)
        assert payout["gross_earnings"] > 0
        assert payout["net_payout"] > 0
        assert "fee_amount" in payout
        assert "meets_minimum" in payout

    def test_estimate_payout_by_platform(self, tracker_with_data):
        payout = tracker_with_data.estimate_payout(platform="amazon", days=30)
        assert payout["gross_earnings"] > 0

    def test_estimate_payout_fees(self, tracker_with_data):
        payout = tracker_with_data.estimate_payout(platform="aliexpress", days=30)
        # AliExpress has 2% fee
        assert payout["fee_rate"] == 0.02

    def test_payout_empty(self, tracker):
        payout = tracker.estimate_payout(days=30)
        assert payout["gross_earnings"] == 0
        assert payout["net_payout"] == 0


class TestTier:
    def test_tier_bronze(self, tracker):
        assert tracker.get_tier() == CommissionTier.BRONZE

    def test_tier_with_data(self, tracker_with_data):
        # ~$12 total commission, should be BRONZE
        tier = tracker_with_data.get_tier()
        assert tier == CommissionTier.BRONZE

    def test_tier_enum_values(self):
        assert CommissionTier.BRONZE.value == "bronze"
        assert CommissionTier.SILVER.value == "silver"
        assert CommissionTier.GOLD.value == "gold"
        assert CommissionTier.PLATINUM.value == "platinum"


class TestGoalTracking:
    def test_create_goal(self, tracker):
        goal = tracker.create_goal("monthly_100", 100.0, period="monthly")
        assert goal.goal_id == "monthly_100"
        assert goal.target_amount == 100.0
        assert goal.current_amount == 0.0
        assert goal.progress == 0.0

    def test_get_goal(self, tracker):
        tracker.create_goal("g1", 500.0, platform="amazon")
        goal = tracker.get_goal("g1")
        assert goal is not None
        assert goal.target_amount == 500.0
        assert goal.platform == "amazon"

    def test_get_nonexistent_goal(self, tracker):
        assert tracker.get_goal("nonexistent") is None

    def test_list_goals(self, tracker):
        tracker.create_goal("g1", 100.0)
        tracker.create_goal("g2", 200.0)
        goals = tracker.list_goals()
        assert len(goals) == 2

    def test_delete_goal(self, tracker):
        tracker.create_goal("g1", 100.0)
        assert tracker.delete_goal("g1")
        assert tracker.get_goal("g1") is None

    def test_delete_nonexistent_goal(self, tracker):
        assert not tracker.delete_goal("nonexistent")

    def test_goal_updates_on_commission(self, tracker):
        tracker.create_goal("g1", 100.0, platform="amazon")
        tracker.record_commission("amazon", 1001, 100.0)  # 4% = $4
        goal = tracker.get_goal("g1")
        assert goal.current_amount == 4.0

    def test_goal_updates_all_platforms(self, tracker):
        tracker.create_goal("g1", 100.0)  # No platform = all
        tracker.record_commission("amazon", 1001, 100.0)  # $4
        tracker.record_commission("shopee", 1001, 100.0)  # $6
        goal = tracker.get_goal("g1")
        assert goal.current_amount == 10.0


class TestEarningsReport:
    def test_generate_report(self, tracker_with_data):
        report = tracker_with_data.generate_report(days=30)
        assert isinstance(report, EarningsReport)
        assert report.total_conversions == 5
        assert report.total_clicks == 30
        assert report.estimated_earnings > 0
        assert len(report.platform_breakdown) == 2

    def test_report_efficiency(self, tracker_with_data):
        report = tracker_with_data.generate_report(days=30)
        assert report.efficiency > 0

    def test_report_empty(self, tracker):
        report = tracker.generate_report(days=30)
        assert report.total_conversions == 0
        assert report.efficiency == 0.0

    def test_report_period_monthly(self, tracker_with_data):
        report = tracker_with_data.generate_report(days=30)
        assert "-" in report.period  # YYYY-MM format

    def test_report_period_weekly(self, tracker_with_data):
        report = tracker_with_data.generate_report(days=7)
        assert "-W" in report.period

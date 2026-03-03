"""Tests for the analytics dashboard engine."""

import pytest
from app.services.analytics_dashboard import (
    AnalyticsDashboard, RevenueData, PlatformMetrics,
    GrowthMetric, TimeGranularity, UserSegment,
    ReportFormat,
)
from datetime import datetime, timezone, timedelta


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "analytics_test.db")


@pytest.fixture
def dashboard(db_path):
    d = AnalyticsDashboard(db_path=db_path)
    yield d
    d.close()


@pytest.fixture
def seeded_dashboard(dashboard):
    """Dashboard with pre-seeded test data."""
    now = datetime.now(timezone.utc)
    for i in range(50):
        ts = (now - timedelta(hours=i)).isoformat()
        platform = ["amazon", "shopee", "aliexpress"][i % 3]
        country = ["US", "CN", "UK", "DE"][i % 4]
        is_conv = 1 if i % 5 == 0 else 0
        revenue = 9.99 if is_conv else 0.0

        dashboard.conn.execute(
            """INSERT INTO click_events
               (user_id, platform, product_id, country, revenue, is_conversion, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1000 + (i % 10), platform, f"PROD{i % 20}", country,
             revenue, is_conv, ts),
        )
    dashboard.conn.commit()
    return dashboard


class TestRevenueData:
    def test_conversion_rate_calculated(self):
        r = RevenueData(period="2026-03-01", clicks=100, conversions=5)
        assert r.conversion_rate == 5.0

    def test_zero_clicks_zero_rate(self):
        r = RevenueData(period="2026-03-01", clicks=0, conversions=0)
        assert r.conversion_rate == 0.0


class TestGrowthMetric:
    def test_positive_growth(self):
        g = GrowthMetric(metric_name="clicks", current_value=200, previous_value=100)
        assert g.change_pct == 100.0
        assert g.trend == "up"

    def test_negative_growth(self):
        g = GrowthMetric(metric_name="clicks", current_value=50, previous_value=100)
        assert g.change_pct == -50.0
        assert g.trend == "down"

    def test_flat_growth(self):
        g = GrowthMetric(metric_name="clicks", current_value=100, previous_value=100)
        assert g.change_pct == 0.0
        assert g.trend == "flat"

    def test_from_zero(self):
        g = GrowthMetric(metric_name="clicks", current_value=50, previous_value=0)
        assert g.change_pct == 100.0
        assert g.trend == "up"

    def test_both_zero(self):
        g = GrowthMetric(metric_name="clicks", current_value=0, previous_value=0)
        assert g.change_pct == 0.0
        assert g.trend == "flat"


class TestPlatformMetrics:
    def test_avg_clicks_per_user(self):
        p = PlatformMetrics(platform="amazon", total_clicks=100, unique_users=10)
        assert p.avg_clicks_per_user == 10.0

    def test_zero_users(self):
        p = PlatformMetrics(platform="amazon", total_clicks=0, unique_users=0)
        assert p.avg_clicks_per_user == 0.0


class TestRecordClick:
    def test_record_click(self, dashboard):
        dashboard.record_click(user_id=1, platform="amazon", product_id="A")
        row = dashboard.conn.execute(
            "SELECT COUNT(*) as cnt FROM click_events"
        ).fetchone()
        assert row["cnt"] == 1

    def test_record_click_with_conversion(self, dashboard):
        dashboard.record_click(
            user_id=1, platform="shopee",
            revenue=15.99, is_conversion=True,
        )
        row = dashboard.conn.execute(
            "SELECT * FROM click_events WHERE user_id = 1"
        ).fetchone()
        assert row["is_conversion"] == 1
        assert row["revenue"] == 15.99


class TestRecordRevenue:
    def test_record_revenue(self, dashboard):
        dashboard.record_revenue(
            platform="amazon", amount=25.50,
            product_id="B0X", order_id="ORD001",
        )
        row = dashboard.conn.execute(
            "SELECT * FROM revenue_log"
        ).fetchone()
        assert row["amount"] == 25.50
        assert row["order_id"] == "ORD001"


class TestRevenueSummary:
    def test_daily_summary(self, seeded_dashboard):
        results = seeded_dashboard.revenue_summary(days=7)
        assert len(results) > 0
        assert all(isinstance(r, RevenueData) for r in results)

    def test_empty_summary(self, dashboard):
        results = dashboard.revenue_summary(days=7)
        assert results == []

    def test_monthly_granularity(self, seeded_dashboard):
        results = seeded_dashboard.revenue_summary(
            days=30, granularity=TimeGranularity.MONTHLY
        )
        assert len(results) > 0

    def test_hourly_granularity(self, seeded_dashboard):
        results = seeded_dashboard.revenue_summary(
            days=3, granularity=TimeGranularity.HOURLY
        )
        assert len(results) > 0


class TestPlatformComparison:
    def test_comparison_with_data(self, seeded_dashboard):
        results = seeded_dashboard.platform_comparison(days=30)
        assert len(results) > 0
        platforms = [r.platform for r in results]
        assert "amazon" in platforms

    def test_comparison_empty(self, dashboard):
        results = dashboard.platform_comparison(days=30)
        assert results == []

    def test_share_sums_to_100(self, seeded_dashboard):
        results = seeded_dashboard.platform_comparison(days=30)
        total_share = sum(r.share_pct for r in results)
        assert abs(total_share - 100.0) < 1.0  # Allow small rounding


class TestTrendingProducts:
    def test_trending_with_data(self, seeded_dashboard):
        products = seeded_dashboard.trending_products(days=7)
        assert len(products) > 0
        assert "product_id" in products[0]
        assert "clicks" in products[0]

    def test_trending_limit(self, seeded_dashboard):
        products = seeded_dashboard.trending_products(days=30, limit=3)
        assert len(products) <= 3

    def test_trending_empty(self, dashboard):
        products = dashboard.trending_products(days=7)
        assert products == []


class TestGeoBreakdown:
    def test_geo_with_data(self, seeded_dashboard):
        geos = seeded_dashboard.geo_breakdown(days=30)
        assert len(geos) > 0
        countries = [g.country for g in geos]
        assert "US" in countries

    def test_geo_share_sums(self, seeded_dashboard):
        geos = seeded_dashboard.geo_breakdown(days=30)
        total = sum(g.share_pct for g in geos)
        assert abs(total - 100.0) < 1.0

    def test_geo_empty(self, dashboard):
        geos = dashboard.geo_breakdown(days=30)
        assert geos == []


class TestUserSegments:
    def test_segments_with_data(self, seeded_dashboard):
        segments = seeded_dashboard.user_segments()
        assert isinstance(segments, dict)
        assert UserSegment.POWER.value in segments
        assert UserSegment.ACTIVE.value in segments

    def test_segments_empty(self, dashboard):
        segments = dashboard.user_segments()
        for seg_list in segments.values():
            assert seg_list == []


class TestGrowthMetrics:
    def test_growth_with_data(self, seeded_dashboard):
        metrics = seeded_dashboard.growth_metrics(days=3)
        assert len(metrics) == 4
        names = [m.metric_name for m in metrics]
        assert "clicks" in names
        assert "revenue" in names

    def test_growth_empty(self, dashboard):
        metrics = dashboard.growth_metrics(days=7)
        assert len(metrics) == 4
        # All should be zero/flat
        for m in metrics:
            assert m.current_value == 0


class TestHeatmaps:
    def test_hourly_heatmap(self, seeded_dashboard):
        heatmap = seeded_dashboard.hourly_heatmap(days=30)
        assert len(heatmap) == 24
        assert all(h in heatmap for h in range(24))
        assert sum(heatmap.values()) > 0

    def test_weekly_heatmap(self, seeded_dashboard):
        heatmap = seeded_dashboard.weekly_heatmap(days=30)
        assert len(heatmap) == 7
        assert all(d in heatmap for d in range(7))

    def test_heatmap_empty(self, dashboard):
        heatmap = dashboard.hourly_heatmap(days=1)
        assert sum(heatmap.values()) == 0


class TestConversionFunnel:
    def test_funnel_with_data(self, seeded_dashboard):
        funnel = seeded_dashboard.conversion_funnel(days=30)
        assert funnel["total_clicks"] > 0
        assert "click_to_conversion_rate" in funnel
        assert "revenue_per_click" in funnel

    def test_funnel_empty(self, dashboard):
        funnel = dashboard.conversion_funnel(days=7)
        assert funnel["total_clicks"] == 0
        assert funnel["click_to_conversion_rate"] == 0

    def test_funnel_rates(self, seeded_dashboard):
        funnel = seeded_dashboard.conversion_funnel(days=30)
        if funnel["total_clicks"] > 0 and funnel["total_conversions"] > 0:
            assert funnel["click_to_conversion_rate"] > 0
            assert funnel["revenue_per_conversion"] > 0


class TestTopUsers:
    def test_top_users_with_data(self, seeded_dashboard):
        users = seeded_dashboard.top_users(days=30)
        assert len(users) > 0
        assert "user_id" in users[0]
        assert "clicks" in users[0]

    def test_top_users_limit(self, seeded_dashboard):
        users = seeded_dashboard.top_users(days=30, limit=3)
        assert len(users) <= 3


class TestReportGeneration:
    def test_text_report(self, seeded_dashboard):
        report = seeded_dashboard.generate_report(days=7, fmt=ReportFormat.TEXT)
        assert "Affiliate Analytics Report" in report
        assert "Conversion Funnel" in report
        assert "Growth" in report

    def test_json_report(self, seeded_dashboard):
        report = seeded_dashboard.generate_report(days=7, fmt=ReportFormat.JSON)
        import json
        data = json.loads(report)
        assert "funnel" in data
        assert "growth" in data
        assert "platforms" in data

    def test_csv_report(self, seeded_dashboard):
        report = seeded_dashboard.generate_report(days=7, fmt=ReportFormat.CSV)
        assert "Metric,Value" in report
        assert "Total Clicks" in report

    def test_empty_report(self, dashboard):
        report = dashboard.generate_report(days=7, fmt=ReportFormat.TEXT)
        assert "Affiliate Analytics Report" in report


class TestEdgeCases:
    def test_single_click(self, dashboard):
        dashboard.record_click(user_id=1, platform="amazon")
        funnel = dashboard.conversion_funnel(days=1)
        assert funnel["total_clicks"] == 1

    def test_all_conversions(self, dashboard):
        for i in range(5):
            dashboard.record_click(
                user_id=i, platform="shopee",
                revenue=10.0, is_conversion=True,
            )
        funnel = dashboard.conversion_funnel(days=1)
        assert funnel["click_to_conversion_rate"] == 100.0

    def test_zero_revenue(self, dashboard):
        dashboard.record_click(user_id=1, platform="amazon")
        funnel = dashboard.conversion_funnel(days=1)
        assert funnel["revenue_per_click"] == 0

    def test_large_dataset(self, dashboard):
        """Test with larger dataset for performance."""
        now = datetime.now(timezone.utc)
        for i in range(200):
            ts = (now - timedelta(minutes=i)).isoformat()
            dashboard.conn.execute(
                """INSERT INTO click_events
                   (user_id, platform, product_id, country, revenue, is_conversion, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (i % 50, "amazon", f"P{i%30}", "US", 0, 0, ts),
            )
        dashboard.conn.commit()

        # All queries should work
        assert dashboard.revenue_summary(days=1)
        assert dashboard.platform_comparison(days=1)
        assert dashboard.trending_products(days=1)
        assert dashboard.conversion_funnel(days=1)["total_clicks"] >= 200

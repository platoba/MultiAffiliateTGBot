"""
Analytics dashboard engine.

Provides comprehensive affiliate performance analytics:
- Revenue summary (daily/weekly/monthly/custom range)
- Conversion funnel analysis (impressions→clicks→conversions→revenue)
- Platform comparison (side-by-side performance metrics)
- Trending products (top performers by clicks/conversions/revenue)
- Geographic breakdown (per-country performance)
- User segment analysis (power users, casual, inactive)
- Growth metrics (MoM, WoW, DoD comparisons)
- Time-of-day heatmap data
- Report generation (text/JSON/CSV)
- SQLite-backed with efficient aggregation queries
"""

import sqlite3
import os
import csv
import json
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class TimeGranularity(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class UserSegment(str, Enum):
    POWER = "power"       # Top 10% by activity
    ACTIVE = "active"     # Active in last 7 days
    CASUAL = "casual"     # Active in last 30 days
    DORMANT = "dormant"   # Inactive 30+ days


class ReportFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    CSV = "csv"


@dataclass
class RevenueData:
    """Revenue aggregation result."""
    period: str  # e.g., "2026-03-01"
    clicks: int = 0
    conversions: int = 0
    estimated_revenue: float = 0.0
    avg_order_value: float = 0.0
    conversion_rate: float = 0.0

    def __post_init__(self):
        if self.clicks > 0 and self.conversions > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100


@dataclass
class PlatformMetrics:
    """Per-platform performance metrics."""
    platform: str
    total_clicks: int = 0
    unique_users: int = 0
    unique_products: int = 0
    avg_clicks_per_user: float = 0.0
    peak_hour: int = -1  # 0-23
    top_product: str = ""
    share_pct: float = 0.0  # Share of total clicks

    def __post_init__(self):
        if self.unique_users > 0:
            self.avg_clicks_per_user = self.total_clicks / self.unique_users


@dataclass
class GeoMetrics:
    """Geographic performance data."""
    country: str
    clicks: int = 0
    users: int = 0
    top_platform: str = ""
    share_pct: float = 0.0


@dataclass
class GrowthMetric:
    """Growth comparison between periods."""
    metric_name: str
    current_value: float = 0.0
    previous_value: float = 0.0
    change_pct: float = 0.0
    trend: str = "flat"  # up, down, flat

    def __post_init__(self):
        if self.previous_value > 0:
            self.change_pct = ((self.current_value - self.previous_value)
                               / self.previous_value) * 100
        elif self.current_value > 0:
            self.change_pct = 100.0

        if self.change_pct > 5:
            self.trend = "up"
        elif self.change_pct < -5:
            self.trend = "down"
        else:
            self.trend = "flat"


class AnalyticsDashboard:
    """
    Affiliate analytics dashboard engine.

    Connects to the main affiliate database to compute
    performance metrics, trends, and reports.
    """

    def __init__(self, db_path: str = "./data/affiliate.db"):
        self.db_path = db_path
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure analytics-specific tables exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                chat_id INTEGER DEFAULT 0,
                chat_title TEXT DEFAULT '',
                original_url TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                product_id TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS click_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                platform TEXT DEFAULT '',
                product_id TEXT DEFAULT '',
                country TEXT DEFAULT '',
                revenue REAL DEFAULT 0.0,
                is_conversion INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS revenue_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                product_id TEXT DEFAULT '',
                user_id INTEGER DEFAULT 0,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                order_id TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_click_events_date ON click_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_click_events_platform ON click_events(platform);
            CREATE INDEX IF NOT EXISTS idx_revenue_date ON revenue_log(created_at);
        """)
        self.conn.commit()

    def record_click(self, user_id: int, platform: str = "",
                     product_id: str = "", country: str = "",
                     revenue: float = 0.0, is_conversion: bool = False):
        """Record a click event for analytics."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO click_events
               (user_id, platform, product_id, country, revenue, is_conversion, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, platform, product_id, country, revenue,
             1 if is_conversion else 0, now),
        )
        self.conn.commit()

    def record_revenue(self, platform: str, amount: float,
                       product_id: str = "", user_id: int = 0,
                       currency: str = "USD", order_id: str = ""):
        """Record a revenue event."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO revenue_log
               (platform, product_id, user_id, amount, currency, order_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (platform, product_id, user_id, amount, currency, order_id, now),
        )
        self.conn.commit()

    def revenue_summary(self, days: int = 30,
                        granularity: TimeGranularity = TimeGranularity.DAILY
                        ) -> list[RevenueData]:
        """Get revenue aggregated by time period."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        if granularity == TimeGranularity.HOURLY:
            date_fmt = "%Y-%m-%d %H:00"
        elif granularity == TimeGranularity.WEEKLY:
            date_fmt = "%Y-W%W"
        elif granularity == TimeGranularity.MONTHLY:
            date_fmt = "%Y-%m"
        else:
            date_fmt = "%Y-%m-%d"

        rows = self.conn.execute(
            f"""SELECT strftime('{date_fmt}', created_at) as period,
                       COUNT(*) as clicks,
                       SUM(is_conversion) as conversions,
                       SUM(revenue) as total_revenue
                FROM click_events
                WHERE created_at >= ?
                GROUP BY period
                ORDER BY period""",
            (cutoff,),
        ).fetchall()

        results = []
        for r in rows:
            conversions = r["conversions"] or 0
            revenue = r["total_revenue"] or 0.0
            avg_ov = revenue / conversions if conversions > 0 else 0.0
            results.append(RevenueData(
                period=r["period"],
                clicks=r["clicks"],
                conversions=conversions,
                estimated_revenue=round(revenue, 2),
                avg_order_value=round(avg_ov, 2),
            ))
        return results

    def platform_comparison(self, days: int = 30) -> list[PlatformMetrics]:
        """Compare performance across platforms."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = self.conn.execute(
            """SELECT platform,
                      COUNT(*) as total_clicks,
                      COUNT(DISTINCT user_id) as unique_users,
                      COUNT(DISTINCT product_id) as unique_products
               FROM click_events
               WHERE created_at >= ? AND platform != ''
               GROUP BY platform
               ORDER BY total_clicks DESC""",
            (cutoff,),
        ).fetchall()

        total_all = sum(r["total_clicks"] for r in rows) or 1
        results = []
        for r in rows:
            # Get peak hour
            peak = self.conn.execute(
                """SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour,
                          COUNT(*) as cnt
                   FROM click_events
                   WHERE platform = ? AND created_at >= ?
                   GROUP BY hour ORDER BY cnt DESC LIMIT 1""",
                (r["platform"], cutoff),
            ).fetchone()

            # Get top product
            top_prod = self.conn.execute(
                """SELECT product_id, COUNT(*) as cnt
                   FROM click_events
                   WHERE platform = ? AND product_id != '' AND created_at >= ?
                   GROUP BY product_id ORDER BY cnt DESC LIMIT 1""",
                (r["platform"], cutoff),
            ).fetchone()

            metrics = PlatformMetrics(
                platform=r["platform"],
                total_clicks=r["total_clicks"],
                unique_users=r["unique_users"],
                unique_products=r["unique_products"],
                peak_hour=peak["hour"] if peak else -1,
                top_product=top_prod["product_id"] if top_prod else "",
                share_pct=round((r["total_clicks"] / total_all) * 100, 1),
            )
            results.append(metrics)

        return results

    def trending_products(self, days: int = 7, limit: int = 20) -> list[dict]:
        """Get trending products by click volume."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = self.conn.execute(
            """SELECT product_id, platform,
                      COUNT(*) as clicks,
                      SUM(is_conversion) as conversions,
                      SUM(revenue) as total_revenue,
                      COUNT(DISTINCT user_id) as unique_users
               FROM click_events
               WHERE product_id != '' AND created_at >= ?
               GROUP BY product_id, platform
               ORDER BY clicks DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

        return [dict(r) for r in rows]

    def geo_breakdown(self, days: int = 30) -> list[GeoMetrics]:
        """Geographic breakdown of clicks."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = self.conn.execute(
            """SELECT country,
                      COUNT(*) as clicks,
                      COUNT(DISTINCT user_id) as users
               FROM click_events
               WHERE country != '' AND created_at >= ?
               GROUP BY country
               ORDER BY clicks DESC""",
            (cutoff,),
        ).fetchall()

        total = sum(r["clicks"] for r in rows) or 1
        results = []
        for r in rows:
            # Get top platform per country
            top = self.conn.execute(
                """SELECT platform, COUNT(*) as cnt
                   FROM click_events
                   WHERE country = ? AND platform != '' AND created_at >= ?
                   GROUP BY platform ORDER BY cnt DESC LIMIT 1""",
                (r["country"], cutoff),
            ).fetchone()

            results.append(GeoMetrics(
                country=r["country"],
                clicks=r["clicks"],
                users=r["users"],
                top_platform=top["platform"] if top else "",
                share_pct=round((r["clicks"] / total) * 100, 1),
            ))
        return results

    def user_segments(self, active_days: int = 7,
                      casual_days: int = 30) -> dict[str, list[int]]:
        """Segment users by activity level."""
        now = datetime.now(timezone.utc)
        active_cutoff = (now - timedelta(days=active_days)).isoformat()
        casual_cutoff = (now - timedelta(days=casual_days)).isoformat()

        # Get all users with click counts
        all_users = self.conn.execute(
            """SELECT user_id, COUNT(*) as clicks,
                      MAX(created_at) as last_click
               FROM click_events
               GROUP BY user_id""",
        ).fetchall()

        segments = {
            UserSegment.POWER.value: [],
            UserSegment.ACTIVE.value: [],
            UserSegment.CASUAL.value: [],
            UserSegment.DORMANT.value: [],
        }

        if not all_users:
            return segments

        # Calculate power threshold (top 10%)
        click_counts = sorted([r["clicks"] for r in all_users], reverse=True)
        power_threshold = click_counts[max(0, len(click_counts) // 10)] if click_counts else 0

        for user in all_users:
            uid = user["user_id"]
            last = user["last_click"]

            if user["clicks"] >= power_threshold and power_threshold > 0:
                segments[UserSegment.POWER.value].append(uid)
            elif last >= active_cutoff:
                segments[UserSegment.ACTIVE.value].append(uid)
            elif last >= casual_cutoff:
                segments[UserSegment.CASUAL.value].append(uid)
            else:
                segments[UserSegment.DORMANT.value].append(uid)

        return segments

    def growth_metrics(self, days: int = 7) -> list[GrowthMetric]:
        """Calculate growth metrics comparing current vs previous period."""
        now = datetime.now(timezone.utc)
        current_start = (now - timedelta(days=days)).isoformat()
        previous_start = (now - timedelta(days=days * 2)).isoformat()

        def _period_stats(start: str, end: str) -> dict:
            row = self.conn.execute(
                """SELECT COUNT(*) as clicks,
                          SUM(is_conversion) as conversions,
                          SUM(revenue) as revenue,
                          COUNT(DISTINCT user_id) as users
                   FROM click_events
                   WHERE created_at >= ? AND created_at < ?""",
                (start, end),
            ).fetchone()
            return {
                "clicks": row["clicks"] or 0,
                "conversions": row["conversions"] or 0,
                "revenue": row["revenue"] or 0.0,
                "users": row["users"] or 0,
            }

        current = _period_stats(current_start, now.isoformat())
        previous = _period_stats(previous_start, current_start)

        metrics = []
        for name in ["clicks", "conversions", "revenue", "users"]:
            metrics.append(GrowthMetric(
                metric_name=name,
                current_value=current[name],
                previous_value=previous[name],
            ))

        return metrics

    def hourly_heatmap(self, days: int = 30) -> dict[int, int]:
        """Get click distribution by hour of day (0-23)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = self.conn.execute(
            """SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour,
                      COUNT(*) as clicks
               FROM click_events
               WHERE created_at >= ?
               GROUP BY hour ORDER BY hour""",
            (cutoff,),
        ).fetchall()

        heatmap = {h: 0 for h in range(24)}
        for r in rows:
            heatmap[r["hour"]] = r["clicks"]
        return heatmap

    def weekly_heatmap(self, days: int = 90) -> dict[int, int]:
        """Get click distribution by day of week (0=Sun, 6=Sat)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = self.conn.execute(
            """SELECT CAST(strftime('%w', created_at) AS INTEGER) as dow,
                      COUNT(*) as clicks
               FROM click_events
               WHERE created_at >= ?
               GROUP BY dow ORDER BY dow""",
            (cutoff,),
        ).fetchall()

        heatmap = {d: 0 for d in range(7)}
        for r in rows:
            heatmap[r["dow"]] = r["clicks"]
        return heatmap

    def conversion_funnel(self, days: int = 30) -> dict:
        """Analyze conversion funnel (clicks → conversions → revenue)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        row = self.conn.execute(
            """SELECT COUNT(*) as total_clicks,
                      SUM(is_conversion) as total_conversions,
                      SUM(revenue) as total_revenue,
                      COUNT(DISTINCT user_id) as total_users,
                      COUNT(DISTINCT product_id) as total_products
               FROM click_events WHERE created_at >= ?""",
            (cutoff,),
        ).fetchone()

        clicks = row["total_clicks"] or 0
        conversions = row["total_conversions"] or 0
        revenue = row["total_revenue"] or 0.0

        return {
            "period_days": days,
            "total_clicks": clicks,
            "total_conversions": conversions,
            "total_revenue": round(revenue, 2),
            "unique_users": row["total_users"] or 0,
            "unique_products": row["total_products"] or 0,
            "click_to_conversion_rate": round(
                (conversions / clicks * 100) if clicks > 0 else 0, 2
            ),
            "revenue_per_click": round(
                revenue / clicks if clicks > 0 else 0, 4
            ),
            "revenue_per_conversion": round(
                revenue / conversions if conversions > 0 else 0, 2
            ),
        }

    def top_users(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Get top users by click volume."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = self.conn.execute(
            """SELECT user_id,
                      COUNT(*) as clicks,
                      SUM(is_conversion) as conversions,
                      SUM(revenue) as revenue,
                      COUNT(DISTINCT platform) as platforms_used
               FROM click_events WHERE created_at >= ?
               GROUP BY user_id
               ORDER BY clicks DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

        return [dict(r) for r in rows]

    def generate_report(self, days: int = 7,
                        fmt: ReportFormat = ReportFormat.TEXT) -> str:
        """Generate a comprehensive analytics report."""
        funnel = self.conversion_funnel(days)
        growth = self.growth_metrics(days)
        platforms = self.platform_comparison(days)
        trending = self.trending_products(days, limit=5)
        top = self.top_users(days, limit=5)

        if fmt == ReportFormat.JSON:
            return json.dumps({
                "period_days": days,
                "funnel": funnel,
                "growth": [
                    {"metric": g.metric_name,
                     "current": g.current_value,
                     "previous": g.previous_value,
                     "change_pct": round(g.change_pct, 1),
                     "trend": g.trend}
                    for g in growth
                ],
                "platforms": [
                    {"platform": p.platform,
                     "clicks": p.total_clicks,
                     "users": p.unique_users,
                     "share": p.share_pct}
                    for p in platforms
                ],
                "trending_products": trending,
                "top_users": top,
            }, indent=2, ensure_ascii=False)

        elif fmt == ReportFormat.CSV:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Period (days)", days])
            writer.writerow(["Total Clicks", funnel["total_clicks"]])
            writer.writerow(["Total Conversions", funnel["total_conversions"]])
            writer.writerow(["Total Revenue", funnel["total_revenue"]])
            writer.writerow(["Conversion Rate %", funnel["click_to_conversion_rate"]])
            writer.writerow(["Revenue/Click", funnel["revenue_per_click"]])
            writer.writerow([])
            writer.writerow(["Platform", "Clicks", "Users", "Share %"])
            for p in platforms:
                writer.writerow([p.platform, p.total_clicks, p.unique_users, p.share_pct])
            return output.getvalue()

        else:  # TEXT
            lines = [
                f"📊 Affiliate Analytics Report ({days} days)",
                "=" * 50,
                "",
                "🔄 Conversion Funnel",
                f"  Clicks: {funnel['total_clicks']:,}",
                f"  Conversions: {funnel['total_conversions']:,}",
                f"  Revenue: ${funnel['total_revenue']:,.2f}",
                f"  Conversion Rate: {funnel['click_to_conversion_rate']}%",
                f"  Rev/Click: ${funnel['revenue_per_click']:.4f}",
                "",
                "📈 Growth (vs previous period)",
            ]
            for g in growth:
                arrow = "↑" if g.trend == "up" else "↓" if g.trend == "down" else "→"
                lines.append(
                    f"  {g.metric_name}: {g.current_value:,.0f} "
                    f"{arrow} {g.change_pct:+.1f}%"
                )

            lines.append("")
            lines.append("🌐 Platform Breakdown")
            for p in platforms:
                lines.append(
                    f"  {p.platform}: {p.total_clicks:,} clicks "
                    f"({p.share_pct}%), {p.unique_users} users"
                )

            if trending:
                lines.append("")
                lines.append("🔥 Trending Products")
                for t in trending[:5]:
                    lines.append(
                        f"  {t['product_id']} ({t['platform']}): "
                        f"{t['clicks']} clicks"
                    )

            return "\n".join(lines)

    def close(self):
        """Close database connection."""
        self.conn.close()

"""
Commission tracking and earnings calculator.

Features:
- Per-platform commission rate configuration
- Earnings tracking per user/platform/period
- Payout estimation with fee deduction
- Monthly/weekly/daily aggregation
- ROI calculation for campaigns
- Goal tracking and progress
- Currency conversion support
- SQLite persistence
"""

import sqlite3
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class PayoutStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


class CommissionTier(str, Enum):
    BRONZE = "bronze"       # < $100/month
    SILVER = "silver"       # $100-$500/month
    GOLD = "gold"           # $500-$2000/month
    PLATINUM = "platinum"   # > $2000/month


@dataclass
class CommissionRate:
    """Commission rate configuration for a platform."""
    platform: str
    base_rate: float          # Base percentage (e.g., 0.04 = 4%)
    bonus_rate: float = 0.0   # Bonus for high performers
    min_payout: float = 10.0  # Minimum payout threshold
    cookie_days: int = 30     # Cookie duration in days
    currency: str = "USD"

    @property
    def effective_rate(self) -> float:
        return self.base_rate + self.bonus_rate

    def estimate_earnings(self, sale_amount: float) -> float:
        return round(sale_amount * self.effective_rate, 2)


@dataclass
class EarningsReport:
    """Aggregated earnings report."""
    period: str           # e.g., "2026-03", "2026-W09", "2026-03-01"
    total_clicks: int = 0
    total_conversions: int = 0
    estimated_earnings: float = 0.0
    actual_earnings: float = 0.0
    platform_breakdown: dict = field(default_factory=dict)
    top_products: list = field(default_factory=list)
    conversion_rate: float = 0.0
    avg_order_value: float = 0.0

    @property
    def efficiency(self) -> float:
        """Earnings per click."""
        if self.total_clicks == 0:
            return 0.0
        return round(self.estimated_earnings / self.total_clicks, 4)


@dataclass
class Goal:
    """Earnings goal."""
    goal_id: str
    target_amount: float
    current_amount: float = 0.0
    period: str = "monthly"  # daily, weekly, monthly
    start_date: str = ""
    platform: str = ""       # empty = all platforms

    @property
    def progress(self) -> float:
        if self.target_amount <= 0:
            return 0.0
        return min(round(self.current_amount / self.target_amount * 100, 1), 100.0)

    @property
    def is_achieved(self) -> bool:
        return self.current_amount >= self.target_amount

    @property
    def remaining(self) -> float:
        return max(0, self.target_amount - self.current_amount)


# Default commission rates by platform
DEFAULT_RATES = {
    "amazon": CommissionRate("amazon", base_rate=0.04, cookie_days=24),
    "shopee": CommissionRate("shopee", base_rate=0.06, cookie_days=7, min_payout=5.0),
    "lazada": CommissionRate("lazada", base_rate=0.05, cookie_days=7, min_payout=5.0),
    "aliexpress": CommissionRate("aliexpress", base_rate=0.07, cookie_days=30),
    "tiktok": CommissionRate("tiktok", base_rate=0.05, cookie_days=14, min_payout=10.0),
}

# Amazon category-specific rates
AMAZON_CATEGORY_RATES = {
    "luxury_beauty": 0.10,
    "amazon_coins": 0.10,
    "digital_music": 0.05,
    "physical_music": 0.05,
    "handmade": 0.05,
    "digital_videos": 0.05,
    "kitchen": 0.045,
    "automotive": 0.045,
    "fashion": 0.04,
    "apparel": 0.04,
    "shoes": 0.04,
    "jewelry": 0.04,
    "luggage": 0.04,
    "electronics": 0.03,
    "computers": 0.025,
    "toys": 0.03,
    "furniture": 0.03,
    "home": 0.03,
    "lawn_garden": 0.03,
    "pets": 0.03,
    "pantry": 0.02,
    "health": 0.01,
    "baby": 0.03,
    "grocery": 0.01,
    "sports": 0.03,
    "outdoors": 0.03,
    "tools": 0.03,
    "video_games": 0.02,
    "default": 0.04,
}


class CommissionTracker:
    """Track affiliate commissions and calculate earnings."""

    def __init__(self, db_path: str = "./data/commissions.db"):
        self.db_path = db_path
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._rates: dict[str, CommissionRate] = dict(DEFAULT_RATES)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS commissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                product_id TEXT DEFAULT '',
                sale_amount REAL DEFAULT 0.0,
                commission_amount REAL DEFAULT 0.0,
                commission_rate REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'pending',
                category TEXT DEFAULT '',
                order_id TEXT DEFAULT '',
                click_id TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                confirmed_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                product_id TEXT DEFAULT '',
                tracking_id TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS payouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                net_amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'pending',
                period TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                paid_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS goals (
                goal_id TEXT PRIMARY KEY,
                target_amount REAL NOT NULL,
                current_amount REAL DEFAULT 0.0,
                period TEXT DEFAULT 'monthly',
                start_date TEXT NOT NULL,
                platform TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_commissions_platform ON commissions(platform);
            CREATE INDEX IF NOT EXISTS idx_commissions_user ON commissions(user_id);
            CREATE INDEX IF NOT EXISTS idx_commissions_date ON commissions(created_at);
            CREATE INDEX IF NOT EXISTS idx_clicks_platform ON clicks(platform);
            CREATE INDEX IF NOT EXISTS idx_clicks_date ON clicks(created_at);
        """)
        self.conn.commit()

    def set_rate(self, platform: str, rate: CommissionRate):
        """Set custom commission rate for a platform."""
        self._rates[platform.lower()] = rate

    def get_rate(self, platform: str, category: str = "") -> CommissionRate:
        """Get commission rate for platform + optional category."""
        platform = platform.lower()
        rate = self._rates.get(platform, CommissionRate(platform, base_rate=0.04))

        # Amazon category-specific rate
        if platform == "amazon" and category:
            cat_rate = AMAZON_CATEGORY_RATES.get(
                category.lower(), AMAZON_CATEGORY_RATES["default"]
            )
            rate = CommissionRate(
                platform=platform,
                base_rate=cat_rate,
                bonus_rate=rate.bonus_rate,
                min_payout=rate.min_payout,
                cookie_days=rate.cookie_days,
                currency=rate.currency,
            )

        return rate

    def record_click(self, platform: str, user_id: int, product_id: str = "",
                     tracking_id: str = ""):
        """Record a click event."""
        self.conn.execute(
            """INSERT INTO clicks (platform, user_id, product_id, tracking_id)
               VALUES (?, ?, ?, ?)""",
            (platform.lower(), user_id, product_id, tracking_id),
        )
        self.conn.commit()

    def record_commission(
        self,
        platform: str,
        user_id: int,
        sale_amount: float,
        product_id: str = "",
        category: str = "",
        order_id: str = "",
        click_id: str = "",
    ) -> float:
        """Record a commission event. Returns estimated commission amount."""
        platform = platform.lower()
        rate = self.get_rate(platform, category)
        commission = rate.estimate_earnings(sale_amount)

        self.conn.execute(
            """INSERT INTO commissions
               (platform, user_id, product_id, sale_amount, commission_amount,
                commission_rate, currency, category, order_id, click_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (platform, user_id, product_id, sale_amount, commission,
             rate.effective_rate, rate.currency, category, order_id, click_id),
        )
        self.conn.commit()

        # Update goal progress
        self._update_goals(platform, commission)

        return commission

    def get_earnings(
        self,
        platform: str = "",
        user_id: int = 0,
        days: int = 30,
    ) -> dict:
        """Get earnings summary for a period."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        where = ["created_at >= ?"]
        params: list = [cutoff]

        if platform:
            where.append("platform = ?")
            params.append(platform.lower())
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)

        where_str = " AND ".join(where)

        row = self.conn.execute(
            f"""SELECT
                COUNT(*) as total_conversions,
                COALESCE(SUM(sale_amount), 0) as total_sales,
                COALESCE(SUM(commission_amount), 0) as total_commission,
                COALESCE(AVG(sale_amount), 0) as avg_order_value,
                COALESCE(AVG(commission_rate), 0) as avg_rate
            FROM commissions WHERE {where_str}""",
            params,
        ).fetchone()

        # Get click count
        click_row = self.conn.execute(
            f"SELECT COUNT(*) as clicks FROM clicks WHERE {where_str}",
            params,
        ).fetchone()

        total_clicks = click_row["clicks"]
        total_conversions = row["total_conversions"]

        return {
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_sales": round(row["total_sales"], 2),
            "total_commission": round(row["total_commission"], 2),
            "avg_order_value": round(row["avg_order_value"], 2),
            "avg_rate": round(row["avg_rate"], 4),
            "conversion_rate": round(
                total_conversions / total_clicks * 100, 2
            ) if total_clicks > 0 else 0.0,
            "days": days,
        }

    def get_platform_breakdown(self, days: int = 30) -> list[dict]:
        """Get earnings breakdown by platform."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        rows = self.conn.execute(
            """SELECT platform,
                COUNT(*) as conversions,
                SUM(sale_amount) as sales,
                SUM(commission_amount) as commission,
                AVG(commission_rate) as avg_rate
            FROM commissions
            WHERE created_at >= ?
            GROUP BY platform
            ORDER BY commission DESC""",
            (cutoff,),
        ).fetchall()

        return [
            {
                "platform": r["platform"],
                "conversions": r["conversions"],
                "sales": round(r["sales"], 2),
                "commission": round(r["commission"], 2),
                "avg_rate": round(r["avg_rate"], 4),
            }
            for r in rows
        ]

    def get_top_products(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Get top earning products."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        rows = self.conn.execute(
            """SELECT product_id, platform,
                COUNT(*) as conversions,
                SUM(commission_amount) as total_commission,
                SUM(sale_amount) as total_sales
            FROM commissions
            WHERE created_at >= ? AND product_id != ''
            GROUP BY product_id, platform
            ORDER BY total_commission DESC
            LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

        return [
            {
                "product_id": r["product_id"],
                "platform": r["platform"],
                "conversions": r["conversions"],
                "total_commission": round(r["total_commission"], 2),
                "total_sales": round(r["total_sales"], 2),
            }
            for r in rows
        ]

    def get_user_leaderboard(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Get top earning users."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        rows = self.conn.execute(
            """SELECT user_id,
                COUNT(*) as conversions,
                SUM(commission_amount) as total_commission,
                COUNT(DISTINCT platform) as platforms_used
            FROM commissions
            WHERE created_at >= ?
            GROUP BY user_id
            ORDER BY total_commission DESC
            LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

        return [
            {
                "user_id": r["user_id"],
                "conversions": r["conversions"],
                "total_commission": round(r["total_commission"], 2),
                "platforms_used": r["platforms_used"],
            }
            for r in rows
        ]

    def get_daily_trend(self, days: int = 30, platform: str = "") -> list[dict]:
        """Get daily earnings trend."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        where = "created_at >= ?"
        params: list = [cutoff]
        if platform:
            where += " AND platform = ?"
            params.append(platform.lower())

        rows = self.conn.execute(
            f"""SELECT DATE(created_at) as day,
                COUNT(*) as conversions,
                SUM(commission_amount) as commission,
                SUM(sale_amount) as sales
            FROM commissions
            WHERE {where}
            GROUP BY DATE(created_at)
            ORDER BY day""",
            params,
        ).fetchall()

        return [
            {
                "date": r["day"],
                "conversions": r["conversions"],
                "commission": round(r["commission"], 2),
                "sales": round(r["sales"], 2),
            }
            for r in rows
        ]

    def estimate_payout(self, platform: str = "", days: int = 30) -> dict:
        """Estimate payout amount after fees."""
        earnings = self.get_earnings(platform=platform, days=days)
        total = earnings["total_commission"]

        # Platform fees (approximate)
        fee_rates = {
            "amazon": 0.0,     # No withdrawal fee
            "shopee": 0.01,    # ~1% processing
            "lazada": 0.01,
            "aliexpress": 0.02,
            "tiktok": 0.0,
        }

        if platform:
            fee_rate = fee_rates.get(platform.lower(), 0.01)
        else:
            fee_rate = 0.01  # Average

        fee = round(total * fee_rate, 2)
        net = round(total - fee, 2)

        # Check minimum payout threshold
        rate = self.get_rate(platform) if platform else CommissionRate("all", 0.04)
        meets_minimum = net >= rate.min_payout

        return {
            "gross_earnings": total,
            "fee_rate": fee_rate,
            "fee_amount": fee,
            "net_payout": net,
            "meets_minimum": meets_minimum,
            "min_payout": rate.min_payout,
            "shortfall": max(0, rate.min_payout - net),
        }

    def get_tier(self, user_id: int = 0) -> CommissionTier:
        """Determine commission tier based on monthly earnings."""
        earnings = self.get_earnings(user_id=user_id, days=30)
        monthly = earnings["total_commission"]

        if monthly >= 2000:
            return CommissionTier.PLATINUM
        elif monthly >= 500:
            return CommissionTier.GOLD
        elif monthly >= 100:
            return CommissionTier.SILVER
        return CommissionTier.BRONZE

    # Goal tracking
    def create_goal(self, goal_id: str, target_amount: float,
                    period: str = "monthly", platform: str = "") -> Goal:
        """Create an earnings goal."""
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            """INSERT OR REPLACE INTO goals
               (goal_id, target_amount, current_amount, period, start_date, platform)
               VALUES (?, ?, 0, ?, ?, ?)""",
            (goal_id, target_amount, period, start_date, platform),
        )
        self.conn.commit()
        return Goal(
            goal_id=goal_id,
            target_amount=target_amount,
            period=period,
            start_date=start_date,
            platform=platform,
        )

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Get a goal by ID."""
        row = self.conn.execute(
            "SELECT * FROM goals WHERE goal_id = ?", (goal_id,)
        ).fetchone()
        if not row:
            return None
        return Goal(
            goal_id=row["goal_id"],
            target_amount=row["target_amount"],
            current_amount=row["current_amount"],
            period=row["period"],
            start_date=row["start_date"],
            platform=row["platform"],
        )

    def list_goals(self) -> list[Goal]:
        """List all goals."""
        rows = self.conn.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()
        return [
            Goal(
                goal_id=r["goal_id"],
                target_amount=r["target_amount"],
                current_amount=r["current_amount"],
                period=r["period"],
                start_date=r["start_date"],
                platform=r["platform"],
            )
            for r in rows
        ]

    def delete_goal(self, goal_id: str) -> bool:
        """Delete a goal."""
        deleted = self.conn.execute(
            "DELETE FROM goals WHERE goal_id = ?", (goal_id,)
        ).rowcount
        self.conn.commit()
        return deleted > 0

    def _update_goals(self, platform: str, amount: float):
        """Update goal progress when commission is recorded."""
        # Update platform-specific goals
        self.conn.execute(
            """UPDATE goals SET current_amount = current_amount + ?
               WHERE (platform = ? OR platform = '')""",
            (amount, platform),
        )
        self.conn.commit()

    def generate_report(self, days: int = 30) -> EarningsReport:
        """Generate a comprehensive earnings report."""
        earnings = self.get_earnings(days=days)
        breakdown = self.get_platform_breakdown(days=days)
        top_products = self.get_top_products(days=days, limit=5)

        period = f"last_{days}_days"
        if days == 30:
            period = datetime.now(timezone.utc).strftime("%Y-%m")
        elif days == 7:
            period = datetime.now(timezone.utc).strftime("%Y-W%W")

        platform_dict = {
            b["platform"]: {
                "conversions": b["conversions"],
                "commission": b["commission"],
                "sales": b["sales"],
            }
            for b in breakdown
        }

        return EarningsReport(
            period=period,
            total_clicks=earnings["total_clicks"],
            total_conversions=earnings["total_conversions"],
            estimated_earnings=earnings["total_commission"],
            platform_breakdown=platform_dict,
            top_products=top_products,
            conversion_rate=earnings["conversion_rate"],
            avg_order_value=earnings["avg_order_value"],
        )

    def close(self):
        self.conn.close()

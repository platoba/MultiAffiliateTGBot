"""
Smart notification engine for affiliate performance alerts.

Features:
- Earnings milestone alerts (first sale, $100, $500, $1000, etc.)
- Performance anomaly detection (sudden traffic spikes/drops)
- Daily/weekly digest generation
- Platform-specific alerts (new platform connected, rate changes)
- Goal progress notifications
- Configurable notification channels (Telegram inline, webhook)
- Quiet hours / DND mode
- Notification history and deduplication
- Priority levels with escalation
- SQLite persistence
"""

import sqlite3
import os
import time
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class NotificationPriority(str, Enum):
    LOW = "low"           # Informational
    MEDIUM = "medium"     # Worth knowing
    HIGH = "high"         # Action needed
    URGENT = "urgent"     # Immediate attention


class NotificationType(str, Enum):
    MILESTONE = "milestone"
    ANOMALY = "anomaly"
    DIGEST = "digest"
    PLATFORM = "platform"
    GOAL = "goal"
    SYSTEM = "system"
    FRAUD = "fraud"
    REVENUE = "revenue"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    DISMISSED = "dismissed"
    FAILED = "failed"


@dataclass
class Notification:
    """A notification to deliver."""
    notification_type: NotificationType
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    user_id: int = 0
    data: dict = field(default_factory=dict)
    dedup_key: str = ""
    notification_id: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if not self.notification_id:
            raw = f"{self.notification_type.value}:{self.title}:{self.created_at}"
            self.notification_id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        if not self.dedup_key:
            self.dedup_key = f"{self.notification_type.value}:{self.title}"


@dataclass
class MilestoneConfig:
    """Milestone threshold configuration."""
    name: str
    threshold: float
    emoji: str = "🎉"
    message_template: str = ""

    def format_message(self, current_value: float) -> str:
        if self.message_template:
            return self.message_template.format(value=current_value,
                                                threshold=self.threshold)
        return f"{self.emoji} Milestone reached: {self.name} = {current_value:.2f} (target: {self.threshold})"


@dataclass
class Goal:
    """User-defined performance goal."""
    goal_id: str
    name: str
    target_value: float
    current_value: float = 0.0
    metric: str = "revenue"  # revenue, clicks, conversions
    deadline: Optional[str] = None  # ISO date
    created_at: str = ""

    @property
    def progress_pct(self) -> float:
        if self.target_value == 0:
            return 0.0
        return min(100.0, (self.current_value / self.target_value) * 100)

    @property
    def is_completed(self) -> bool:
        return self.current_value >= self.target_value


@dataclass
class QuietHours:
    """DND / quiet hours configuration."""
    enabled: bool = False
    start_hour: int = 22  # 10 PM
    end_hour: int = 8     # 8 AM
    timezone_offset: int = 0  # UTC offset in hours

    def is_quiet_now(self) -> bool:
        if not self.enabled:
            return False
        now = datetime.now(timezone.utc) + timedelta(hours=self.timezone_offset)
        hour = now.hour
        if self.start_hour > self.end_hour:
            return hour >= self.start_hour or hour < self.end_hour
        return self.start_hour <= hour < self.end_hour


# Default milestones
DEFAULT_MILESTONES = [
    MilestoneConfig("First Click", 1, "🎯", "🎯 First affiliate click recorded!"),
    MilestoneConfig("10 Clicks", 10, "🔟", "🔟 You've hit 10 affiliate clicks!"),
    MilestoneConfig("100 Clicks", 100, "💯", "💯 100 clicks milestone!"),
    MilestoneConfig("1K Clicks", 1000, "🚀", "🚀 1,000 clicks! You're on fire!"),
    MilestoneConfig("First Sale", 0.01, "💰", "💰 First affiliate sale! Revenue: ${value:.2f}"),
    MilestoneConfig("$10 Revenue", 10, "💵", "💵 $10 revenue milestone!"),
    MilestoneConfig("$100 Revenue", 100, "🤑", "🤑 $100 revenue milestone!"),
    MilestoneConfig("$500 Revenue", 500, "🏆", "🏆 $500 revenue! Impressive!"),
    MilestoneConfig("$1000 Revenue", 1000, "👑", "👑 $1,000 revenue! You're a pro!"),
]


class NotificationEngine:
    """
    Smart notification engine.

    Generates, deduplicates, and delivers performance notifications.
    """

    def __init__(self, db_path: str = "./data/notifications.db",
                 quiet_hours: Optional[QuietHours] = None,
                 milestones: Optional[list[MilestoneConfig]] = None,
                 dedup_window_hours: int = 24):
        self.db_path = db_path
        self.quiet_hours = quiet_hours or QuietHours()
        self.milestones = milestones or DEFAULT_MILESTONES
        self.dedup_window = dedup_window_hours
        self._handlers: list[Callable[[Notification], bool]] = []
        self._pending: list[Notification] = []
        self._achieved_milestones: set[str] = set()

        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        self._load_achieved_milestones()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                notification_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                user_id INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                dedup_key TEXT DEFAULT '',
                data_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                sent_at TEXT DEFAULT NULL,
                read_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS milestones_achieved (
                milestone_name TEXT PRIMARY KEY,
                achieved_at TEXT NOT NULL DEFAULT (datetime('now')),
                value_at_achievement REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS goals (
                goal_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                target_value REAL NOT NULL,
                current_value REAL DEFAULT 0.0,
                metric TEXT DEFAULT 'revenue',
                deadline TEXT DEFAULT NULL,
                is_completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS anomaly_baselines (
                metric TEXT PRIMARY KEY,
                avg_value REAL DEFAULT 0.0,
                std_dev REAL DEFAULT 0.0,
                sample_count INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_notif_type ON notifications(notification_type);
            CREATE INDEX IF NOT EXISTS idx_notif_status ON notifications(status);
            CREATE INDEX IF NOT EXISTS idx_notif_date ON notifications(created_at);
        """)
        self.conn.commit()

    def _load_achieved_milestones(self):
        rows = self.conn.execute(
            "SELECT milestone_name FROM milestones_achieved"
        ).fetchall()
        self._achieved_milestones = {r["milestone_name"] for r in rows}

    def register_handler(self, handler: Callable[[Notification], bool]):
        """Register a notification delivery handler."""
        self._handlers.append(handler)

    def check_milestones(self, metric: str, current_value: float) -> list[Notification]:
        """Check if any milestones have been reached."""
        notifications = []

        for milestone in self.milestones:
            if milestone.name in self._achieved_milestones:
                continue

            # Match milestone to metric
            is_click_milestone = "click" in milestone.name.lower()
            is_revenue_milestone = ("$" in milestone.name or
                                    "sale" in milestone.name.lower() or
                                    "revenue" in milestone.name.lower())

            if metric == "clicks" and is_click_milestone:
                if current_value >= milestone.threshold:
                    notif = self._create_milestone_notification(
                        milestone, current_value)
                    notifications.append(notif)
            elif metric == "revenue" and is_revenue_milestone:
                if current_value >= milestone.threshold:
                    notif = self._create_milestone_notification(
                        milestone, current_value)
                    notifications.append(notif)

        return notifications

    def _create_milestone_notification(self, milestone: MilestoneConfig,
                                       value: float) -> Notification:
        """Create and record a milestone notification."""
        self._achieved_milestones.add(milestone.name)
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR IGNORE INTO milestones_achieved
               (milestone_name, achieved_at, value_at_achievement)
               VALUES (?, ?, ?)""",
            (milestone.name, now, value),
        )
        self.conn.commit()

        body = milestone.format_message(value)
        return Notification(
            notification_type=NotificationType.MILESTONE,
            title=f"Milestone: {milestone.name}",
            body=body,
            priority=NotificationPriority.HIGH,
            dedup_key=f"milestone:{milestone.name}",
        )

    def check_anomaly(self, metric: str, current_value: float,
                      threshold_sigma: float = 2.0) -> Optional[Notification]:
        """Check if current value is anomalous compared to baseline."""
        row = self.conn.execute(
            "SELECT * FROM anomaly_baselines WHERE metric = ?",
            (metric,),
        ).fetchone()

        if not row or row["sample_count"] < 5:
            # Not enough data for baseline
            self._update_baseline(metric, current_value)
            return None

        avg = row["avg_value"]
        std = row["std_dev"]
        self._update_baseline(metric, current_value)

        if std == 0:
            return None

        z_score = (current_value - avg) / std

        if abs(z_score) >= threshold_sigma:
            direction = "spike" if z_score > 0 else "drop"
            emoji = "📈" if z_score > 0 else "📉"
            priority = (NotificationPriority.HIGH if abs(z_score) >= 3
                        else NotificationPriority.MEDIUM)

            return Notification(
                notification_type=NotificationType.ANOMALY,
                title=f"Traffic {direction} detected",
                body=(f"{emoji} {metric} {direction}: {current_value:.0f} "
                      f"(avg: {avg:.0f}, z-score: {z_score:.1f})"),
                priority=priority,
                data={"metric": metric, "value": current_value,
                      "avg": avg, "z_score": round(z_score, 2)},
            )

        return None

    def _update_baseline(self, metric: str, value: float):
        """Update anomaly baseline with new data point (running stats)."""
        row = self.conn.execute(
            "SELECT * FROM anomaly_baselines WHERE metric = ?",
            (metric,),
        ).fetchone()

        now = datetime.now(timezone.utc).isoformat()

        if not row:
            self.conn.execute(
                """INSERT INTO anomaly_baselines
                   (metric, avg_value, std_dev, sample_count, updated_at)
                   VALUES (?, ?, 0, 1, ?)""",
                (metric, value, now),
            )
        else:
            n = row["sample_count"]
            old_avg = row["avg_value"]
            old_std = row["std_dev"]

            new_n = n + 1
            new_avg = old_avg + (value - old_avg) / new_n
            # Welford's online algorithm for variance
            new_std = (((old_std ** 2 * n) +
                        (value - old_avg) * (value - new_avg)) / new_n) ** 0.5

            self.conn.execute(
                """UPDATE anomaly_baselines
                   SET avg_value = ?, std_dev = ?, sample_count = ?, updated_at = ?
                   WHERE metric = ?""",
                (new_avg, new_std, new_n, now, metric),
            )

        self.conn.commit()

    def generate_daily_digest(self, clicks_today: int = 0,
                              conversions_today: int = 0,
                              revenue_today: float = 0.0,
                              top_platform: str = "",
                              top_product: str = "") -> Notification:
        """Generate daily performance digest."""
        lines = [
            "📊 Daily Affiliate Digest",
            "",
            f"🖱️ Clicks: {clicks_today:,}",
            f"🛒 Conversions: {conversions_today:,}",
            f"💰 Revenue: ${revenue_today:,.2f}",
        ]

        if clicks_today > 0:
            rate = (conversions_today / clicks_today * 100) if clicks_today else 0
            lines.append(f"📈 Conversion Rate: {rate:.1f}%")

        if top_platform:
            lines.append(f"🏆 Top Platform: {top_platform}")
        if top_product:
            lines.append(f"🔥 Top Product: {top_product}")

        return Notification(
            notification_type=NotificationType.DIGEST,
            title="Daily Digest",
            body="\n".join(lines),
            priority=NotificationPriority.LOW,
            data={
                "clicks": clicks_today,
                "conversions": conversions_today,
                "revenue": revenue_today,
            },
        )

    def generate_weekly_digest(self, weekly_stats: dict) -> Notification:
        """Generate weekly performance summary."""
        clicks = weekly_stats.get("clicks", 0)
        conversions = weekly_stats.get("conversions", 0)
        revenue = weekly_stats.get("revenue", 0.0)
        growth = weekly_stats.get("growth_pct", 0.0)

        arrow = "↑" if growth > 0 else "↓" if growth < 0 else "→"
        emoji = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"

        lines = [
            "📊 Weekly Affiliate Summary",
            "",
            f"🖱️ Total Clicks: {clicks:,}",
            f"🛒 Conversions: {conversions:,}",
            f"💰 Revenue: ${revenue:,.2f}",
            f"{emoji} Growth: {arrow} {abs(growth):.1f}% vs last week",
        ]

        return Notification(
            notification_type=NotificationType.DIGEST,
            title="Weekly Summary",
            body="\n".join(lines),
            priority=NotificationPriority.MEDIUM,
            data=weekly_stats,
        )

    # --- Goal Management ---

    def create_goal(self, name: str, target_value: float,
                    metric: str = "revenue",
                    deadline: Optional[str] = None) -> Goal:
        """Create a new performance goal."""
        goal_id = hashlib.sha256(
            f"{name}:{target_value}:{time.time()}".encode()
        ).hexdigest()[:8]

        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO goals
               (goal_id, name, target_value, metric, deadline, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (goal_id, name, target_value, metric, deadline, now),
        )
        self.conn.commit()

        return Goal(
            goal_id=goal_id, name=name,
            target_value=target_value, metric=metric,
            deadline=deadline, created_at=now,
        )

    def update_goal_progress(self, goal_id: str,
                             current_value: float) -> Optional[Notification]:
        """Update goal progress, returns notification if goal completed."""
        row = self.conn.execute(
            "SELECT * FROM goals WHERE goal_id = ?", (goal_id,),
        ).fetchone()

        if not row or row["is_completed"]:
            return None

        self.conn.execute(
            "UPDATE goals SET current_value = ? WHERE goal_id = ?",
            (current_value, goal_id),
        )

        if current_value >= row["target_value"]:
            now = datetime.now(timezone.utc).isoformat()
            self.conn.execute(
                """UPDATE goals SET is_completed = 1, completed_at = ?
                   WHERE goal_id = ?""",
                (now, goal_id),
            )
            self.conn.commit()

            return Notification(
                notification_type=NotificationType.GOAL,
                title=f"🎯 Goal Completed: {row['name']}",
                body=(f"🎯 You've reached your goal!\n"
                      f"Goal: {row['name']}\n"
                      f"Target: {row['target_value']:.2f}\n"
                      f"Achieved: {current_value:.2f}"),
                priority=NotificationPriority.HIGH,
                data={"goal_id": goal_id, "target": row["target_value"],
                      "achieved": current_value},
            )

        self.conn.commit()
        return None

    def list_goals(self, include_completed: bool = False) -> list[Goal]:
        """List all goals."""
        query = "SELECT * FROM goals"
        if not include_completed:
            query += " WHERE is_completed = 0"
        query += " ORDER BY created_at DESC"

        rows = self.conn.execute(query).fetchall()
        return [
            Goal(
                goal_id=r["goal_id"], name=r["name"],
                target_value=r["target_value"],
                current_value=r["current_value"],
                metric=r["metric"], deadline=r["deadline"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def delete_goal(self, goal_id: str) -> bool:
        """Delete a goal."""
        cursor = self.conn.execute(
            "DELETE FROM goals WHERE goal_id = ?", (goal_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # --- Notification Delivery ---

    def send(self, notification: Notification) -> bool:
        """Send a notification through registered handlers."""
        # Check quiet hours
        if (self.quiet_hours.is_quiet_now() and
                notification.priority != NotificationPriority.URGENT):
            self._pending.append(notification)
            self._save_notification(notification, NotificationStatus.PENDING)
            return False

        # Check dedup
        if self._is_duplicate(notification):
            return False

        # Save to DB
        self._save_notification(notification, NotificationStatus.SENT)

        # Deliver through handlers
        delivered = False
        for handler in self._handlers:
            try:
                if handler(notification):
                    delivered = True
            except Exception:
                pass

        if not delivered and not self._handlers:
            # No handlers registered, but still recorded
            delivered = True

        return delivered

    def send_batch(self, notifications: list[Notification]) -> int:
        """Send multiple notifications. Returns count of sent."""
        sent = 0
        for notif in notifications:
            if self.send(notif):
                sent += 1
        return sent

    def flush_pending(self) -> int:
        """Send all pending notifications (call after quiet hours end)."""
        sent = 0
        pending = list(self._pending)
        self._pending.clear()

        for notif in pending:
            if self.send(notif):
                sent += 1
        return sent

    def _is_duplicate(self, notification: Notification) -> bool:
        """Check if notification is a duplicate within dedup window."""
        if not notification.dedup_key:
            return False

        cutoff = (datetime.now(timezone.utc) -
                  timedelta(hours=self.dedup_window)).isoformat()

        row = self.conn.execute(
            """SELECT COUNT(*) as cnt FROM notifications
               WHERE dedup_key = ? AND created_at >= ? AND status = 'sent'""",
            (notification.dedup_key, cutoff),
        ).fetchone()

        return (row["cnt"] or 0) > 0

    def _save_notification(self, notification: Notification,
                           status: NotificationStatus):
        """Persist notification to database."""
        import json as _json
        now = datetime.now(timezone.utc).isoformat()
        sent_at = now if status == NotificationStatus.SENT else None

        self.conn.execute(
            """INSERT OR IGNORE INTO notifications
               (id, notification_type, title, body, priority, user_id,
                status, dedup_key, data_json, created_at, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (notification.notification_id,
             notification.notification_type.value,
             notification.title, notification.body,
             notification.priority.value, notification.user_id,
             status.value, notification.dedup_key,
             _json.dumps(notification.data, ensure_ascii=False),
             now, sent_at),
        )
        self.conn.commit()

    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE notifications SET status = 'read', read_at = ? WHERE id = ?",
            (now, notification_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def dismiss(self, notification_id: str) -> bool:
        """Dismiss a notification."""
        cursor = self.conn.execute(
            "UPDATE notifications SET status = 'dismissed' WHERE id = ?",
            (notification_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_unread(self, limit: int = 50) -> list[dict]:
        """Get unread notifications."""
        rows = self.conn.execute(
            """SELECT * FROM notifications
               WHERE status IN ('sent', 'pending')
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_history(self, days: int = 7, limit: int = 100) -> list[dict]:
        """Get notification history."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT * FROM notifications
               WHERE created_at >= ?
               ORDER BY created_at DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Get notification statistics."""
        rows = self.conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM notifications GROUP BY status""",
        ).fetchall()

        by_type = self.conn.execute(
            """SELECT notification_type, COUNT(*) as cnt
               FROM notifications GROUP BY notification_type""",
        ).fetchall()

        return {
            "by_status": {r["status"]: r["cnt"] for r in rows},
            "by_type": {r["notification_type"]: r["cnt"] for r in by_type},
            "total_milestones": len(self._achieved_milestones),
            "pending_count": len(self._pending),
            "quiet_hours_active": self.quiet_hours.is_quiet_now(),
        }

    def cleanup(self, days: int = 90):
        """Remove old notifications."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        self.conn.execute(
            "DELETE FROM notifications WHERE created_at < ?", (cutoff,),
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()

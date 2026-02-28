"""
SQLite-backed analytics database.
Replaces the JSON file approach for better concurrency and querying.
"""

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


class Database:
    """SQLite analytics database for affiliate link tracking."""

    def __init__(self, db_path: str = "./data/affiliate.db"):
        self.db_path = db_path
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """Create tables if they don't exist."""
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

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                total_conversions INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                is_blocked INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT DEFAULT '',
                is_enabled INTEGER DEFAULT 1,
                total_conversions INTEGER DEFAULT 0,
                added_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_conversions_platform ON conversions(platform);
            CREATE INDEX IF NOT EXISTS idx_conversions_user ON conversions(user_id);
            CREATE INDEX IF NOT EXISTS idx_conversions_date ON conversions(created_at);
            CREATE INDEX IF NOT EXISTS idx_conversions_chat ON conversions(chat_id);
        """)
        self.conn.commit()

    def record_conversion(
        self,
        platform: str,
        user_id: int,
        username: str,
        chat_id: int,
        chat_title: str,
        original_url: str,
        affiliate_url: str,
        product_id: str = "",
    ):
        """Record a link conversion event."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO conversions
               (platform, user_id, username, chat_id, chat_title, original_url, affiliate_url, product_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (platform, user_id, username, chat_id, chat_title,
             original_url[:500], affiliate_url[:500], product_id, now),
        )

        # Upsert user
        self.conn.execute(
            """INSERT INTO users (user_id, username, first_name, total_conversions, first_seen, last_seen)
               VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username = excluded.username,
                 total_conversions = total_conversions + 1,
                 last_seen = excluded.last_seen""",
            (user_id, username, username, now, now),
        )

        # Upsert group (only for group chats)
        if chat_id < 0:
            self.conn.execute(
                """INSERT INTO groups (chat_id, chat_title, total_conversions, added_at)
                   VALUES (?, ?, 1, ?)
                   ON CONFLICT(chat_id) DO UPDATE SET
                     chat_title = excluded.chat_title,
                     total_conversions = total_conversions + 1""",
                (chat_id, chat_title, now),
            )
        self.conn.commit()

    def get_total_stats(self) -> dict:
        """Get overall statistics."""
        row = self.conn.execute("SELECT COUNT(*) as total FROM conversions").fetchone()
        total = row["total"]

        # Platform breakdown
        platforms = {}
        for row in self.conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM conversions GROUP BY platform ORDER BY cnt DESC"
        ):
            platforms[row["platform"]] = row["cnt"]

        # Today's count
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM conversions WHERE created_at >= ?",
            (today,),
        ).fetchone()

        # This week
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        week_row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM conversions WHERE created_at >= ?",
            (week_ago,),
        ).fetchone()

        return {
            "total": total,
            "today": today_row["cnt"],
            "this_week": week_row["cnt"],
            "by_platform": platforms,
        }

    def get_top_users(self, limit: int = 10) -> list[dict]:
        """Get top users by conversion count."""
        rows = self.conn.execute(
            """SELECT user_id, username, total_conversions, last_seen
               FROM users WHERE is_blocked = 0
               ORDER BY total_conversions DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_user_stats(self, user_id: int) -> Optional[dict]:
        """Get stats for a specific user."""
        row = self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None

        # Platform breakdown for user
        platforms = {}
        for prow in self.conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM conversions WHERE user_id = ? GROUP BY platform",
            (user_id,),
        ):
            platforms[prow["platform"]] = prow["cnt"]

        return {**dict(row), "by_platform": platforms}

    def get_daily_stats(self, days: int = 7) -> list[dict]:
        """Get daily conversion counts."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            """SELECT date(created_at) as day, COUNT(*) as cnt
               FROM conversions WHERE created_at >= ?
               GROUP BY day ORDER BY day""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_group_stats(self) -> list[dict]:
        """Get stats for all groups."""
        rows = self.conn.execute(
            "SELECT * FROM groups ORDER BY total_conversions DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_conversions(self, limit: int = 20) -> list[dict]:
        """Get recent conversions."""
        rows = self.conn.execute(
            """SELECT platform, username, original_url, affiliate_url, product_id, created_at
               FROM conversions ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def block_user(self, user_id: int):
        """Block a user from using the bot."""
        self.conn.execute(
            "UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()

    def unblock_user(self, user_id: int):
        """Unblock a user."""
        self.conn.execute(
            "UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()

    def is_user_blocked(self, user_id: int) -> bool:
        """Check if user is blocked."""
        row = self.conn.execute(
            "SELECT is_blocked FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return bool(row and row["is_blocked"])

    def set_group_enabled(self, chat_id: int, enabled: bool):
        """Enable/disable bot in a group."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO groups (chat_id, is_enabled, added_at)
               VALUES (?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET is_enabled = ?""",
            (chat_id, int(enabled), now, int(enabled)),
        )
        self.conn.commit()

    def is_group_enabled(self, chat_id: int) -> bool:
        """Check if bot is enabled in a group."""
        row = self.conn.execute(
            "SELECT is_enabled FROM groups WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return not row or bool(row["is_enabled"])

    def export_conversions(self, days: int = 30) -> list[dict]:
        """Export conversions for CSV/JSON."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT platform, user_id, username, chat_id, chat_title,
                      original_url, affiliate_url, product_id, created_at
               FROM conversions WHERE created_at >= ?
               ORDER BY id DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()

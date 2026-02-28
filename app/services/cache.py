"""
Link cache to avoid re-converting the same URL.
Uses SQLite for persistence with TTL support.
"""

import sqlite3
import os
import time
from pathlib import Path
from typing import Optional


class LinkCache:
    """URL conversion cache with TTL."""

    def __init__(self, db_path: str = "./data/cache.db", ttl_hours: int = 24):
        self.ttl_seconds = ttl_hours * 3600
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                url_hash TEXT PRIMARY KEY,
                original_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                product_id TEXT DEFAULT '',
                cached_at REAL NOT NULL
            )
        """)
        self.conn.commit()

    def get(self, url: str) -> Optional[dict]:
        """Get cached conversion, returns None if expired or missing."""
        url_hash = self._hash(url)
        row = self.conn.execute(
            "SELECT * FROM cache WHERE url_hash = ?", (url_hash,)
        ).fetchone()

        if not row:
            return None

        # Check TTL
        if time.time() - row["cached_at"] > self.ttl_seconds:
            self.conn.execute("DELETE FROM cache WHERE url_hash = ?", (url_hash,))
            self.conn.commit()
            return None

        return dict(row)

    def put(self, url: str, platform: str, affiliate_url: str, product_id: str = ""):
        """Cache a conversion result."""
        url_hash = self._hash(url)
        self.conn.execute(
            """INSERT OR REPLACE INTO cache
               (url_hash, original_url, platform, affiliate_url, product_id, cached_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url_hash, url[:500], platform, affiliate_url[:500], product_id, time.time()),
        )
        self.conn.commit()

    def cleanup(self):
        """Remove expired entries."""
        cutoff = time.time() - self.ttl_seconds
        deleted = self.conn.execute(
            "DELETE FROM cache WHERE cached_at < ?", (cutoff,)
        ).rowcount
        self.conn.commit()
        return deleted

    def size(self) -> int:
        """Number of cached entries."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM cache").fetchone()
        return row["cnt"]

    def _hash(self, url: str) -> str:
        """Create a hash for URL lookup."""
        import hashlib
        return hashlib.md5(url.strip().lower().encode()).hexdigest()

    def close(self):
        self.conn.close()

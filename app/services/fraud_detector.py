"""
Click fraud detection engine.

Detects and mitigates fraudulent affiliate link activity:
- Velocity-based click flood detection (per user/IP/chat)
- Bot signature pattern matching (known UA strings, headless markers)
- Duplicate click fingerprinting (same user+product in short window)
- Geographic anomaly detection (impossible travel speed)
- Session pattern analysis (too-regular intervals = bot)
- Risk scoring (0-100) with configurable thresholds
- Auto-block and quarantine
- Fraud report generation
- SQLite persistence with evidence trail
"""

import sqlite3
import os
import time
import hashlib
import math
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class RiskLevel(str, Enum):
    CLEAN = "clean"           # 0-20
    LOW = "low"               # 21-40
    MEDIUM = "medium"         # 41-60
    HIGH = "high"             # 61-80
    CRITICAL = "critical"     # 81-100


class FraudType(str, Enum):
    CLICK_FLOOD = "click_flood"
    BOT_SIGNATURE = "bot_signature"
    DUPLICATE_CLICK = "duplicate_click"
    GEO_ANOMALY = "geo_anomaly"
    REGULAR_INTERVAL = "regular_interval"
    SUSPICIOUS_REFERRER = "suspicious_referrer"
    DEVICE_MISMATCH = "device_mismatch"
    PROXY_DETECTED = "proxy_detected"


class ActionType(str, Enum):
    ALLOW = "allow"
    FLAG = "flag"
    THROTTLE = "throttle"
    BLOCK = "block"
    QUARANTINE = "quarantine"


@dataclass
class ClickEvent:
    """A single click event to analyze."""
    user_id: int
    chat_id: int = 0
    platform: str = ""
    product_id: str = ""
    url: str = ""
    ip_address: str = ""
    user_agent: str = ""
    referrer: str = ""
    country: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timestamp: float = 0.0  # epoch seconds

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def fingerprint(self) -> str:
        """Generate click fingerprint for dedup."""
        raw = f"{self.user_id}:{self.platform}:{self.product_id}:{self.ip_address}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class FraudSignal:
    """A detected fraud signal."""
    fraud_type: FraudType
    score: float  # 0-100 contribution
    evidence: str
    confidence: float = 0.0  # 0.0-1.0


@dataclass
class FraudVerdict:
    """Final fraud assessment for a click."""
    click: ClickEvent
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.CLEAN
    action: ActionType = ActionType.ALLOW
    signals: list = field(default_factory=list)
    checked_at: float = 0.0

    def __post_init__(self):
        if self.checked_at == 0.0:
            self.checked_at = time.time()

    @property
    def is_fraudulent(self) -> bool:
        return self.risk_score > 60

    @property
    def signal_summary(self) -> str:
        if not self.signals:
            return "No fraud signals"
        parts = [f"{s.fraud_type.value}({s.score:.0f})" for s in self.signals]
        return ", ".join(parts)


# Known bot user-agent signatures
BOT_SIGNATURES = [
    "bot", "crawler", "spider", "scraper", "headless",
    "phantomjs", "selenium", "puppeteer", "playwright",
    "wget", "curl", "python-requests", "httpie",
    "go-http-client", "java/", "libwww-perl",
    "mechanize", "httpclient", "aiohttp",
    "node-fetch", "axios/", "got/",
]

# Known datacenter/proxy ASN indicators
PROXY_INDICATORS = [
    "datacenter", "hosting", "cloud", "vpn", "proxy",
    "tor", "tunnel", "anonymizer",
]


class FraudDetector:
    """
    Multi-signal click fraud detection engine.

    Combines velocity checks, bot detection, geo analysis,
    and pattern matching to produce a risk score (0-100).
    """

    def __init__(self, db_path: str = "./data/fraud.db",
                 velocity_window_seconds: int = 60,
                 velocity_max_clicks: int = 10,
                 dedup_window_seconds: int = 300,
                 geo_max_speed_kmh: float = 1000.0,
                 auto_block_threshold: float = 80.0,
                 auto_throttle_threshold: float = 50.0):
        self.db_path = db_path
        self.velocity_window = velocity_window_seconds
        self.velocity_max = velocity_max_clicks
        self.dedup_window = dedup_window_seconds
        self.geo_max_speed = geo_max_speed_kmh
        self.block_threshold = auto_block_threshold
        self.throttle_threshold = auto_throttle_threshold

        # In-memory click buffer for velocity checks
        self._click_buffer: dict[int, list[float]] = defaultdict(list)
        # In-memory fingerprint dedup
        self._fingerprints: dict[str, float] = {}
        # Blocked users set
        self._blocked_users: set[int] = set()
        # Quarantined users (temporary)
        self._quarantined: dict[int, float] = {}

        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        self._load_blocked()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS fraud_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER DEFAULT 0,
                platform TEXT DEFAULT '',
                product_id TEXT DEFAULT '',
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                action_taken TEXT NOT NULL,
                signals TEXT DEFAULT '',
                fingerprint TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                country TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT DEFAULT '',
                blocked_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS fraud_stats (
                date TEXT PRIMARY KEY,
                total_checks INTEGER DEFAULT 0,
                total_flagged INTEGER DEFAULT 0,
                total_blocked INTEGER DEFAULT 0,
                avg_risk_score REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_fraud_user ON fraud_events(user_id);
            CREATE INDEX IF NOT EXISTS idx_fraud_date ON fraud_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_fraud_level ON fraud_events(risk_level);
        """)
        self.conn.commit()

    def _load_blocked(self):
        """Load blocked users from DB."""
        rows = self.conn.execute("SELECT user_id FROM blocked_users").fetchall()
        self._blocked_users = {row["user_id"] for row in rows}

    def analyze(self, click: ClickEvent) -> FraudVerdict:
        """
        Analyze a click event for fraud signals.

        Returns a FraudVerdict with risk score and recommended action.
        """
        signals: list[FraudSignal] = []

        # Check if user is already blocked
        if click.user_id in self._blocked_users:
            return FraudVerdict(
                click=click,
                risk_score=100.0,
                risk_level=RiskLevel.CRITICAL,
                action=ActionType.BLOCK,
                signals=[FraudSignal(
                    fraud_type=FraudType.CLICK_FLOOD,
                    score=100.0,
                    evidence="User is on block list",
                    confidence=1.0,
                )],
            )

        # Check quarantine
        if click.user_id in self._quarantined:
            if time.time() < self._quarantined[click.user_id]:
                return FraudVerdict(
                    click=click,
                    risk_score=75.0,
                    risk_level=RiskLevel.HIGH,
                    action=ActionType.THROTTLE,
                    signals=[FraudSignal(
                        fraud_type=FraudType.CLICK_FLOOD,
                        score=75.0,
                        evidence="User is in quarantine",
                        confidence=0.9,
                    )],
                )
            else:
                del self._quarantined[click.user_id]

        # 1. Velocity check
        vel_signal = self._check_velocity(click)
        if vel_signal:
            signals.append(vel_signal)

        # 2. Bot signature check
        bot_signal = self._check_bot_signature(click)
        if bot_signal:
            signals.append(bot_signal)

        # 3. Duplicate click check
        dup_signal = self._check_duplicate(click)
        if dup_signal:
            signals.append(dup_signal)

        # 4. Geographic anomaly check
        geo_signal = self._check_geo_anomaly(click)
        if geo_signal:
            signals.append(geo_signal)

        # 5. Regular interval pattern
        interval_signal = self._check_regular_interval(click)
        if interval_signal:
            signals.append(interval_signal)

        # 6. Suspicious referrer
        ref_signal = self._check_referrer(click)
        if ref_signal:
            signals.append(ref_signal)

        # Calculate total risk score (capped at 100)
        total_score = min(100.0, sum(s.score * s.confidence for s in signals))
        risk_level = self._score_to_level(total_score)
        action = self._determine_action(total_score, click.user_id)

        verdict = FraudVerdict(
            click=click,
            risk_score=round(total_score, 1),
            risk_level=risk_level,
            action=action,
            signals=signals,
        )

        # Record and enforce
        self._record_event(verdict)
        self._enforce(verdict)

        # Update click buffer
        self._click_buffer[click.user_id].append(click.timestamp)

        return verdict

    def _check_velocity(self, click: ClickEvent) -> Optional[FraudSignal]:
        """Check click velocity (too many clicks in short window)."""
        now = click.timestamp
        cutoff = now - self.velocity_window
        user_clicks = self._click_buffer.get(click.user_id, [])
        recent = [t for t in user_clicks if t > cutoff]
        self._click_buffer[click.user_id] = recent

        count = len(recent)
        if count >= self.velocity_max:
            ratio = count / self.velocity_max
            score = min(50.0, 20.0 * ratio)
            return FraudSignal(
                fraud_type=FraudType.CLICK_FLOOD,
                score=score,
                evidence=f"{count} clicks in {self.velocity_window}s (max: {self.velocity_max})",
                confidence=min(1.0, ratio * 0.5),
            )
        return None

    def _check_bot_signature(self, click: ClickEvent) -> Optional[FraudSignal]:
        """Check user-agent for bot signatures."""
        if not click.user_agent:
            return None

        ua_lower = click.user_agent.lower()
        matched = [sig for sig in BOT_SIGNATURES if sig in ua_lower]

        if matched:
            score = min(40.0, 20.0 * len(matched))
            return FraudSignal(
                fraud_type=FraudType.BOT_SIGNATURE,
                score=score,
                evidence=f"Bot signatures: {', '.join(matched)}",
                confidence=0.85,
            )
        return None

    def _check_duplicate(self, click: ClickEvent) -> Optional[FraudSignal]:
        """Check for duplicate clicks (same fingerprint in dedup window)."""
        fp = click.fingerprint
        now = click.timestamp

        # Clean old fingerprints
        cutoff = now - self.dedup_window
        expired = [k for k, v in self._fingerprints.items() if v < cutoff]
        for k in expired:
            del self._fingerprints[k]

        if fp in self._fingerprints:
            elapsed = now - self._fingerprints[fp]
            score = max(10.0, 30.0 - (elapsed / self.dedup_window) * 20.0)
            self._fingerprints[fp] = now
            return FraudSignal(
                fraud_type=FraudType.DUPLICATE_CLICK,
                score=score,
                evidence=f"Duplicate click fingerprint, {elapsed:.0f}s apart",
                confidence=0.7,
            )

        self._fingerprints[fp] = now
        return None

    def _check_geo_anomaly(self, click: ClickEvent) -> Optional[FraudSignal]:
        """Check for impossible travel (geo too far in too little time)."""
        if click.latitude == 0.0 and click.longitude == 0.0:
            return None

        # Get last known location for user
        row = self.conn.execute(
            """SELECT country, created_at FROM fraud_events
               WHERE user_id = ? AND country != ''
               ORDER BY created_at DESC LIMIT 1""",
            (click.user_id,)
        ).fetchone()

        if not row or not row["country"]:
            return None

        if row["country"] != click.country and click.country:
            # Different country - check time gap
            try:
                last_time = datetime.fromisoformat(row["created_at"])
                now_time = datetime.now(timezone.utc)
                hours = max(0.01, (now_time - last_time).total_seconds() / 3600)
                if hours < 2:  # Country change in < 2 hours
                    score = min(35.0, 35.0 / hours)
                    return FraudSignal(
                        fraud_type=FraudType.GEO_ANOMALY,
                        score=score,
                        evidence=f"Country changed {row['country']}→{click.country} in {hours:.1f}h",
                        confidence=0.6,
                    )
            except (ValueError, TypeError):
                pass

        return None

    def _check_regular_interval(self, click: ClickEvent) -> Optional[FraudSignal]:
        """Detect suspiciously regular click intervals (bot behavior)."""
        user_clicks = self._click_buffer.get(click.user_id, [])
        if len(user_clicks) < 5:
            return None

        # Calculate intervals between last 10 clicks
        recent = sorted(user_clicks[-10:])
        intervals = [recent[i+1] - recent[i] for i in range(len(recent)-1)]

        if len(intervals) < 4:
            return None

        mean = statistics.mean(intervals)
        if mean == 0:
            return FraudSignal(
                fraud_type=FraudType.REGULAR_INTERVAL,
                score=40.0,
                evidence="Zero-interval burst detected",
                confidence=0.9,
            )

        try:
            stdev = statistics.stdev(intervals)
        except statistics.StatisticsError:
            return None

        cv = stdev / mean if mean > 0 else 0  # coefficient of variation

        if cv < 0.1 and mean < 10:  # Very regular, fast clicks
            score = min(35.0, 35.0 * (1 - cv))
            return FraudSignal(
                fraud_type=FraudType.REGULAR_INTERVAL,
                score=score,
                evidence=f"Regular intervals: mean={mean:.1f}s, CV={cv:.3f}",
                confidence=0.75,
            )

        return None

    def _check_referrer(self, click: ClickEvent) -> Optional[FraudSignal]:
        """Check for suspicious referrer patterns."""
        if not click.referrer:
            return None

        ref_lower = click.referrer.lower()
        suspicious = ["fiverr.com", "freelancer.com", "clickfarm",
                      "trafficbot", "hitforge", "jingling"]

        for s in suspicious:
            if s in ref_lower:
                return FraudSignal(
                    fraud_type=FraudType.SUSPICIOUS_REFERRER,
                    score=45.0,
                    evidence=f"Suspicious referrer: {click.referrer}",
                    confidence=0.9,
                )

        return None

    def _score_to_level(self, score: float) -> RiskLevel:
        if score <= 20:
            return RiskLevel.CLEAN
        elif score <= 40:
            return RiskLevel.LOW
        elif score <= 60:
            return RiskLevel.MEDIUM
        elif score <= 80:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _determine_action(self, score: float, user_id: int) -> ActionType:
        if score >= self.block_threshold:
            return ActionType.BLOCK
        elif score >= self.throttle_threshold:
            return ActionType.THROTTLE
        elif score > 20:
            return ActionType.FLAG
        return ActionType.ALLOW

    def _enforce(self, verdict: FraudVerdict):
        """Auto-enforce action based on verdict."""
        if verdict.action == ActionType.BLOCK:
            self.block_user(verdict.click.user_id,
                            reason=verdict.signal_summary)
        elif verdict.action == ActionType.QUARANTINE:
            self._quarantined[verdict.click.user_id] = time.time() + 3600

    def _record_event(self, verdict: FraudVerdict):
        """Persist fraud event to database."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO fraud_events
               (user_id, chat_id, platform, product_id, risk_score,
                risk_level, action_taken, signals, fingerprint,
                ip_address, user_agent, country, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (verdict.click.user_id, verdict.click.chat_id,
             verdict.click.platform, verdict.click.product_id,
             verdict.risk_score, verdict.risk_level.value,
             verdict.action.value, verdict.signal_summary,
             verdict.click.fingerprint, verdict.click.ip_address,
             verdict.click.user_agent, verdict.click.country, now),
        )
        self.conn.commit()

        # Update daily stats
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            """INSERT INTO fraud_stats (date, total_checks, total_flagged, total_blocked, avg_risk_score)
               VALUES (?, 1, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   total_checks = total_checks + 1,
                   total_flagged = total_flagged + ?,
                   total_blocked = total_blocked + ?,
                   avg_risk_score = (avg_risk_score * (total_checks - 1) + ?) / total_checks""",
            (date,
             1 if verdict.risk_score > 20 else 0,
             1 if verdict.action == ActionType.BLOCK else 0,
             verdict.risk_score,
             1 if verdict.risk_score > 20 else 0,
             1 if verdict.action == ActionType.BLOCK else 0,
             verdict.risk_score),
        )
        self.conn.commit()

    def block_user(self, user_id: int, reason: str = "",
                   duration_hours: Optional[float] = None) -> bool:
        """Block a user. Optional duration (permanent if None)."""
        now = datetime.now(timezone.utc).isoformat()
        expires = None
        if duration_hours:
            expires = (datetime.now(timezone.utc) +
                       timedelta(hours=duration_hours)).isoformat()

        self.conn.execute(
            """INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, reason, now, expires),
        )
        self.conn.commit()
        self._blocked_users.add(user_id)
        return True

    def unblock_user(self, user_id: int) -> bool:
        """Unblock a user."""
        self.conn.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        self._blocked_users.discard(user_id)
        return True

    def is_blocked(self, user_id: int) -> bool:
        """Check if user is blocked."""
        return user_id in self._blocked_users

    def get_user_risk_history(self, user_id: int, limit: int = 50) -> list[dict]:
        """Get recent fraud events for a user."""
        rows = self.conn.execute(
            """SELECT * FROM fraud_events WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_user_risk_score(self, user_id: int) -> float:
        """Calculate average risk score for a user."""
        row = self.conn.execute(
            "SELECT AVG(risk_score) as avg_score FROM fraud_events WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return round(row["avg_score"], 1) if row and row["avg_score"] else 0.0

    def get_daily_stats(self, days: int = 7) -> list[dict]:
        """Get fraud stats for recent days."""
        rows = self.conn.execute(
            """SELECT * FROM fraud_stats
               ORDER BY date DESC LIMIT ?""",
            (days,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_top_offenders(self, limit: int = 10) -> list[dict]:
        """Get users with highest average risk scores."""
        rows = self.conn.execute(
            """SELECT user_id, COUNT(*) as events,
                      AVG(risk_score) as avg_score,
                      MAX(risk_score) as max_score,
                      SUM(CASE WHEN action_taken = 'block' THEN 1 ELSE 0 END) as blocks
               FROM fraud_events
               GROUP BY user_id
               HAVING events >= 3
               ORDER BY avg_score DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def generate_report(self, days: int = 7) -> dict:
        """Generate fraud detection summary report."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        total = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM fraud_events WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()

        by_level = self.conn.execute(
            """SELECT risk_level, COUNT(*) as cnt
               FROM fraud_events WHERE created_at >= ?
               GROUP BY risk_level ORDER BY cnt DESC""",
            (cutoff,),
        ).fetchall()

        by_type = self.conn.execute(
            """SELECT signals, COUNT(*) as cnt
               FROM fraud_events WHERE risk_score > 20 AND created_at >= ?
               GROUP BY signals ORDER BY cnt DESC LIMIT 10""",
            (cutoff,),
        ).fetchall()

        avg_score = self.conn.execute(
            "SELECT AVG(risk_score) as avg FROM fraud_events WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()

        return {
            "period_days": days,
            "total_checks": total["cnt"] if total else 0,
            "by_risk_level": {r["risk_level"]: r["cnt"] for r in by_level},
            "top_signal_patterns": [
                {"signals": r["signals"], "count": r["cnt"]} for r in by_type
            ],
            "avg_risk_score": round(avg_score["avg"], 1) if avg_score and avg_score["avg"] else 0.0,
            "blocked_users": len(self._blocked_users),
            "quarantined_users": len(self._quarantined),
        }

    def cleanup(self, days: int = 90):
        """Remove old fraud events."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        self.conn.execute("DELETE FROM fraud_events WHERE created_at < ?", (cutoff,))
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()

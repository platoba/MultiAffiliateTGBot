"""
A/B testing for affiliate links.

Features:
- Split testing between different affiliate IDs/tags
- Conversion rate comparison per variant
- Automatic winner selection with statistical significance
- Campaign management (create, pause, stop, archive)
- Traffic allocation control (50/50, 70/30, etc.)
- SQLite persistence
"""

import sqlite3
import os
import math
import time
import random
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Variant:
    """A variant in an A/B test."""
    variant_id: str
    name: str
    affiliate_tag: str           # The affiliate ID/tag to use
    traffic_weight: float = 0.5  # Traffic allocation (0.0-1.0)
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0

    @property
    def ctr(self) -> float:
        """Click-through rate."""
        if self.impressions == 0:
            return 0.0
        return round(self.clicks / self.impressions * 100, 2)

    @property
    def conversion_rate(self) -> float:
        """Conversion rate (conversions / clicks)."""
        if self.clicks == 0:
            return 0.0
        return round(self.conversions / self.clicks * 100, 2)

    @property
    def revenue_per_click(self) -> float:
        """Revenue per click (RPC)."""
        if self.clicks == 0:
            return 0.0
        return round(self.revenue / self.clicks, 4)

    @property
    def revenue_per_impression(self) -> float:
        """Revenue per mille (RPM)."""
        if self.impressions == 0:
            return 0.0
        return round(self.revenue / self.impressions * 1000, 2)

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "affiliate_tag": self.affiliate_tag,
            "traffic_weight": self.traffic_weight,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "revenue": self.revenue,
            "ctr": self.ctr,
            "conversion_rate": self.conversion_rate,
            "revenue_per_click": self.revenue_per_click,
        }


@dataclass
class Experiment:
    """An A/B test experiment."""
    experiment_id: str
    name: str
    platform: str
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: list[Variant] = field(default_factory=list)
    confidence_threshold: float = 0.95  # 95% confidence
    min_sample_size: int = 100          # Minimum clicks per variant
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    winner_variant_id: str = ""
    metric: str = "conversion_rate"     # What to optimize

    @property
    def total_impressions(self) -> int:
        return sum(v.impressions for v in self.variants)

    @property
    def total_clicks(self) -> int:
        return sum(v.clicks for v in self.variants)

    @property
    def total_conversions(self) -> int:
        return sum(v.conversions for v in self.variants)

    @property
    def total_revenue(self) -> float:
        return round(sum(v.revenue for v in self.variants), 2)

    @property
    def is_significant(self) -> bool:
        """Check if we have enough data for significance."""
        return all(v.clicks >= self.min_sample_size for v in self.variants)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "platform": self.platform,
            "status": self.status.value,
            "variants": [v.to_dict() for v in self.variants],
            "total_impressions": self.total_impressions,
            "total_clicks": self.total_clicks,
            "total_conversions": self.total_conversions,
            "total_revenue": self.total_revenue,
            "is_significant": self.is_significant,
            "winner_variant_id": self.winner_variant_id,
            "created_at": self.created_at,
        }


@dataclass
class SignificanceResult:
    """Result of statistical significance test."""
    is_significant: bool
    confidence: float           # 0.0-1.0
    z_score: float
    p_value: float
    winner_id: str
    loser_id: str
    lift: float                 # Percentage improvement
    sample_sufficient: bool

    def to_dict(self) -> dict:
        return {
            "is_significant": self.is_significant,
            "confidence": round(self.confidence, 4),
            "z_score": round(self.z_score, 4),
            "p_value": round(self.p_value, 6),
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "lift": round(self.lift, 2),
            "sample_sufficient": self.sample_sufficient,
        }


class ABTestManager:
    """Manage A/B tests for affiliate links."""

    def __init__(self, db_path: str = "./data/ab_tests.db"):
        self.db_path = db_path
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                confidence_threshold REAL DEFAULT 0.95,
                min_sample_size INTEGER DEFAULT 100,
                metric TEXT DEFAULT 'conversion_rate',
                winner_variant_id TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                started_at TEXT DEFAULT '',
                completed_at TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS variants (
                variant_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                name TEXT NOT NULL,
                affiliate_tag TEXT NOT NULL,
                traffic_weight REAL DEFAULT 0.5,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                revenue REAL DEFAULT 0.0,
                PRIMARY KEY (variant_id, experiment_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                user_id INTEGER DEFAULT 0,
                value REAL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_experiment ON events(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_events_variant ON events(variant_id);
            CREATE INDEX IF NOT EXISTS idx_variants_experiment ON variants(experiment_id);
        """)
        self.conn.commit()

    def create_experiment(
        self,
        name: str,
        platform: str,
        variants: list[dict],
        confidence_threshold: float = 0.95,
        min_sample_size: int = 100,
        metric: str = "conversion_rate",
    ) -> Experiment:
        """Create a new A/B test experiment.

        Args:
            name: Experiment name
            platform: Platform being tested
            variants: List of dicts with 'name', 'affiliate_tag', optional 'traffic_weight'
            confidence_threshold: Statistical significance threshold
            min_sample_size: Minimum clicks per variant
            metric: Metric to optimize (conversion_rate, revenue_per_click, ctr)
        """
        if len(variants) < 2:
            raise ValueError("Need at least 2 variants for A/B test")
        if len(variants) > 5:
            raise ValueError("Maximum 5 variants allowed")

        experiment_id = hashlib.md5(
            f"{name}:{platform}:{time.time()}".encode()
        ).hexdigest()[:12]

        # Normalize traffic weights
        total_weight = sum(v.get("traffic_weight", 1.0 / len(variants)) for v in variants)
        variant_objects = []
        for i, v in enumerate(variants):
            vid = f"v{i}"
            weight = v.get("traffic_weight", 1.0 / len(variants)) / total_weight
            variant_objects.append(Variant(
                variant_id=vid,
                name=v["name"],
                affiliate_tag=v["affiliate_tag"],
                traffic_weight=round(weight, 4),
            ))

        # Save experiment
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            """INSERT INTO experiments
               (experiment_id, name, platform, status, confidence_threshold,
                min_sample_size, metric, created_at)
               VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)""",
            (experiment_id, name, platform, confidence_threshold,
             min_sample_size, metric, now),
        )

        # Save variants
        for v in variant_objects:
            self.conn.execute(
                """INSERT INTO variants
                   (variant_id, experiment_id, name, affiliate_tag, traffic_weight)
                   VALUES (?, ?, ?, ?, ?)""",
                (v.variant_id, experiment_id, v.name, v.affiliate_tag, v.traffic_weight),
            )

        self.conn.commit()

        return Experiment(
            experiment_id=experiment_id,
            name=name,
            platform=platform,
            variants=variant_objects,
            confidence_threshold=confidence_threshold,
            min_sample_size=min_sample_size,
            metric=metric,
            created_at=now,
        )

    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment (change status to running)."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        updated = self.conn.execute(
            """UPDATE experiments SET status = 'running', started_at = ?
               WHERE experiment_id = ? AND status IN ('draft', 'paused')""",
            (now, experiment_id),
        ).rowcount
        self.conn.commit()
        return updated > 0

    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause a running experiment."""
        updated = self.conn.execute(
            """UPDATE experiments SET status = 'paused'
               WHERE experiment_id = ? AND status = 'running'""",
            (experiment_id,),
        ).rowcount
        self.conn.commit()
        return updated > 0

    def complete_experiment(self, experiment_id: str, winner_id: str = "") -> bool:
        """Complete an experiment."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Auto-detect winner if not specified
        if not winner_id:
            exp = self.get_experiment(experiment_id)
            if exp and exp.variants:
                sig = self.check_significance(experiment_id)
                if sig and sig.is_significant:
                    winner_id = sig.winner_id

        updated = self.conn.execute(
            """UPDATE experiments SET status = 'completed', completed_at = ?,
               winner_variant_id = ?
               WHERE experiment_id = ? AND status IN ('running', 'paused')""",
            (now, winner_id, experiment_id),
        ).rowcount
        self.conn.commit()
        return updated > 0

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment with variants."""
        row = self.conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        if not row:
            return None

        variant_rows = self.conn.execute(
            "SELECT * FROM variants WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchall()

        variants = [
            Variant(
                variant_id=v["variant_id"],
                name=v["name"],
                affiliate_tag=v["affiliate_tag"],
                traffic_weight=v["traffic_weight"],
                impressions=v["impressions"],
                clicks=v["clicks"],
                conversions=v["conversions"],
                revenue=v["revenue"],
            )
            for v in variant_rows
        ]

        return Experiment(
            experiment_id=row["experiment_id"],
            name=row["name"],
            platform=row["platform"],
            status=ExperimentStatus(row["status"]),
            variants=variants,
            confidence_threshold=row["confidence_threshold"],
            min_sample_size=row["min_sample_size"],
            metric=row["metric"],
            winner_variant_id=row["winner_variant_id"],
            created_at=row["created_at"],
            started_at=row["started_at"] or "",
            completed_at=row["completed_at"] or "",
        )

    def list_experiments(self, status: str = "") -> list[Experiment]:
        """List experiments, optionally filtered by status."""
        if status:
            rows = self.conn.execute(
                "SELECT experiment_id FROM experiments WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT experiment_id FROM experiments ORDER BY created_at DESC"
            ).fetchall()

        return [
            self.get_experiment(r["experiment_id"])
            for r in rows
            if self.get_experiment(r["experiment_id"]) is not None
        ]

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment and its data."""
        self.conn.execute(
            "DELETE FROM events WHERE experiment_id = ?", (experiment_id,)
        )
        self.conn.execute(
            "DELETE FROM variants WHERE experiment_id = ?", (experiment_id,)
        )
        deleted = self.conn.execute(
            "DELETE FROM experiments WHERE experiment_id = ?", (experiment_id,)
        ).rowcount
        self.conn.commit()
        return deleted > 0

    def assign_variant(self, experiment_id: str, user_id: int = 0) -> Optional[Variant]:
        """Assign a user to a variant based on traffic weights.

        Uses consistent hashing so same user always gets same variant.
        """
        exp = self.get_experiment(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return None

        if not exp.variants:
            return None

        # Consistent hash for user assignment
        if user_id:
            hash_input = f"{experiment_id}:{user_id}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            ratio = (hash_val % 10000) / 10000.0
        else:
            ratio = random.random()

        # Select variant based on weights
        cumulative = 0.0
        for variant in exp.variants:
            cumulative += variant.traffic_weight
            if ratio <= cumulative:
                return variant

        # Fallback to last variant
        return exp.variants[-1]

    def record_impression(self, experiment_id: str, variant_id: str, user_id: int = 0):
        """Record an impression for a variant."""
        self.conn.execute(
            """UPDATE variants SET impressions = impressions + 1
               WHERE experiment_id = ? AND variant_id = ?""",
            (experiment_id, variant_id),
        )
        self.conn.execute(
            """INSERT INTO events (experiment_id, variant_id, event_type, user_id)
               VALUES (?, ?, 'impression', ?)""",
            (experiment_id, variant_id, user_id),
        )
        self.conn.commit()

    def record_click(self, experiment_id: str, variant_id: str, user_id: int = 0):
        """Record a click for a variant."""
        self.conn.execute(
            """UPDATE variants SET clicks = clicks + 1
               WHERE experiment_id = ? AND variant_id = ?""",
            (experiment_id, variant_id),
        )
        self.conn.execute(
            """INSERT INTO events (experiment_id, variant_id, event_type, user_id)
               VALUES (?, ?, 'click', ?)""",
            (experiment_id, variant_id, user_id),
        )
        self.conn.commit()

    def record_conversion(self, experiment_id: str, variant_id: str,
                          revenue: float = 0.0, user_id: int = 0):
        """Record a conversion for a variant."""
        self.conn.execute(
            """UPDATE variants SET conversions = conversions + 1, revenue = revenue + ?
               WHERE experiment_id = ? AND variant_id = ?""",
            (revenue, experiment_id, variant_id),
        )
        self.conn.execute(
            """INSERT INTO events (experiment_id, variant_id, event_type, user_id, value)
               VALUES (?, ?, 'conversion', ?, ?)""",
            (experiment_id, variant_id, user_id, revenue),
        )
        self.conn.commit()

        # Auto-check for winner
        self._auto_complete_check(experiment_id)

    def check_significance(self, experiment_id: str) -> Optional[SignificanceResult]:
        """Check statistical significance between variants using Z-test.

        Uses two-proportion Z-test for conversion rate comparison.
        """
        exp = self.get_experiment(experiment_id)
        if not exp or len(exp.variants) < 2:
            return None

        # Sort variants by the optimization metric
        if exp.metric == "revenue_per_click":
            sorted_variants = sorted(exp.variants, key=lambda v: v.revenue_per_click, reverse=True)
        elif exp.metric == "ctr":
            sorted_variants = sorted(exp.variants, key=lambda v: v.ctr, reverse=True)
        else:
            sorted_variants = sorted(exp.variants, key=lambda v: v.conversion_rate, reverse=True)

        best = sorted_variants[0]
        second = sorted_variants[1]

        # Check sample size
        sample_sufficient = all(
            v.clicks >= exp.min_sample_size for v in [best, second]
        )

        if best.clicks == 0 or second.clicks == 0:
            return SignificanceResult(
                is_significant=False,
                confidence=0.0,
                z_score=0.0,
                p_value=1.0,
                winner_id=best.variant_id,
                loser_id=second.variant_id,
                lift=0.0,
                sample_sufficient=False,
            )

        # Two-proportion Z-test
        p1 = best.conversions / best.clicks
        p2 = second.conversions / second.clicks
        n1 = best.clicks
        n2 = second.clicks

        # Pooled proportion
        p_pool = (best.conversions + second.conversions) / (n1 + n2)

        if p_pool == 0 or p_pool == 1:
            return SignificanceResult(
                is_significant=False,
                confidence=0.0,
                z_score=0.0,
                p_value=1.0,
                winner_id=best.variant_id,
                loser_id=second.variant_id,
                lift=0.0,
                sample_sufficient=sample_sufficient,
            )

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))

        if se == 0:
            return SignificanceResult(
                is_significant=False,
                confidence=0.0,
                z_score=0.0,
                p_value=1.0,
                winner_id=best.variant_id,
                loser_id=second.variant_id,
                lift=0.0,
                sample_sufficient=sample_sufficient,
            )

        z_score = (p1 - p2) / se

        # Approximate p-value using normal CDF
        p_value = self._normal_cdf(-abs(z_score)) * 2  # two-tailed

        confidence = 1.0 - p_value

        # Calculate lift
        lift = ((p1 - p2) / p2 * 100) if p2 > 0 else 0.0

        return SignificanceResult(
            is_significant=confidence >= exp.confidence_threshold and sample_sufficient,
            confidence=confidence,
            z_score=z_score,
            p_value=p_value,
            winner_id=best.variant_id,
            loser_id=second.variant_id,
            lift=lift,
            sample_sufficient=sample_sufficient,
        )

    def get_recommendation(self, experiment_id: str) -> dict:
        """Get a recommendation for the experiment."""
        exp = self.get_experiment(experiment_id)
        if not exp:
            return {"action": "not_found", "message": "Experiment not found"}

        sig = self.check_significance(experiment_id)
        if not sig:
            return {"action": "error", "message": "Cannot calculate significance"}

        if exp.status == ExperimentStatus.COMPLETED:
            winner = next((v for v in exp.variants if v.variant_id == exp.winner_variant_id), None)
            return {
                "action": "completed",
                "message": f"Experiment completed. Winner: {winner.name if winner else 'N/A'}",
                "winner": winner.to_dict() if winner else None,
            }

        if not sig.sample_sufficient:
            min_needed = max(exp.min_sample_size - min(v.clicks for v in exp.variants), 0)
            return {
                "action": "collect_more_data",
                "message": f"Need ~{min_needed} more clicks for significance",
                "current_leader": sig.winner_id,
                "confidence": sig.confidence,
            }

        if sig.is_significant:
            winner = next((v for v in exp.variants if v.variant_id == sig.winner_id), None)
            return {
                "action": "declare_winner",
                "message": f"Winner found with {sig.confidence:.1%} confidence! "
                          f"Lift: {sig.lift:+.1f}%",
                "winner": winner.to_dict() if winner else None,
                "significance": sig.to_dict(),
            }

        return {
            "action": "no_winner_yet",
            "message": f"No significant difference yet (confidence: {sig.confidence:.1%})",
            "current_leader": sig.winner_id,
            "confidence": sig.confidence,
        }

    def _auto_complete_check(self, experiment_id: str):
        """Auto-complete experiment if winner is found."""
        exp = self.get_experiment(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return

        sig = self.check_significance(experiment_id)
        if sig and sig.is_significant and sig.sample_sufficient:
            self.complete_experiment(experiment_id, winner_id=sig.winner_id)

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate normal CDF using error function approximation."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def close(self):
        self.conn.close()

"""Tests for A/B testing manager."""

import pytest
from app.services.ab_testing import (
    ABTestManager,
    Experiment,
    ExperimentStatus,
    Variant,
    SignificanceResult,
)


@pytest.fixture
def manager(tmp_path):
    db = str(tmp_path / "ab_tests.db")
    m = ABTestManager(db_path=db)
    yield m
    m.close()


@pytest.fixture
def running_experiment(manager):
    """Create and start a running experiment."""
    exp = manager.create_experiment(
        name="Amazon Tag Test",
        platform="amazon",
        variants=[
            {"name": "Control", "affiliate_tag": "tag-20", "traffic_weight": 0.5},
            {"name": "Variant B", "affiliate_tag": "newtag-20", "traffic_weight": 0.5},
        ],
    )
    manager.start_experiment(exp.experiment_id)
    return exp


@pytest.fixture
def experiment_with_data(running_experiment, manager):
    """Running experiment with recorded events."""
    exp = running_experiment
    v0, v1 = "v0", "v1"

    # Variant 0 (Control): 200 clicks, 20 conversions (10%)
    for _ in range(200):
        manager.record_impression(exp.experiment_id, v0)
        manager.record_click(exp.experiment_id, v0)
    for _ in range(20):
        manager.record_conversion(exp.experiment_id, v0, revenue=50.0)

    # Variant 1: 200 clicks, 30 conversions (15%)
    for _ in range(200):
        manager.record_impression(exp.experiment_id, v1)
        manager.record_click(exp.experiment_id, v1)
    for _ in range(30):
        manager.record_conversion(exp.experiment_id, v1, revenue=45.0)

    return exp


class TestVariant:
    def test_ctr(self):
        v = Variant("v0", "Control", "tag-20", impressions=1000, clicks=50)
        assert v.ctr == 5.0

    def test_ctr_zero_impressions(self):
        v = Variant("v0", "Control", "tag-20")
        assert v.ctr == 0.0

    def test_conversion_rate(self):
        v = Variant("v0", "Control", "tag-20", clicks=100, conversions=10)
        assert v.conversion_rate == 10.0

    def test_conversion_rate_zero_clicks(self):
        v = Variant("v0", "Control", "tag-20")
        assert v.conversion_rate == 0.0

    def test_revenue_per_click(self):
        v = Variant("v0", "Control", "tag-20", clicks=100, revenue=500.0)
        assert v.revenue_per_click == 5.0

    def test_revenue_per_click_zero(self):
        v = Variant("v0", "Control", "tag-20")
        assert v.revenue_per_click == 0.0

    def test_rpm(self):
        v = Variant("v0", "Control", "tag-20", impressions=1000, revenue=50.0)
        assert v.revenue_per_impression == 50.0  # $50 per 1000 impressions

    def test_to_dict(self):
        v = Variant("v0", "Control", "tag-20", clicks=100, conversions=10, revenue=500.0)
        d = v.to_dict()
        assert d["variant_id"] == "v0"
        assert d["name"] == "Control"
        assert d["affiliate_tag"] == "tag-20"
        assert d["conversion_rate"] == 10.0
        assert d["revenue_per_click"] == 5.0


class TestExperiment:
    def test_total_stats(self):
        exp = Experiment(
            experiment_id="e1",
            name="Test",
            platform="amazon",
            variants=[
                Variant("v0", "A", "t1", clicks=100, conversions=10, impressions=1000, revenue=500),
                Variant("v1", "B", "t2", clicks=150, conversions=20, impressions=1500, revenue=800),
            ],
        )
        assert exp.total_impressions == 2500
        assert exp.total_clicks == 250
        assert exp.total_conversions == 30
        assert exp.total_revenue == 1300.0

    def test_is_significant_needs_data(self):
        exp = Experiment(
            experiment_id="e1",
            name="Test",
            platform="amazon",
            min_sample_size=100,
            variants=[
                Variant("v0", "A", "t1", clicks=50),
                Variant("v1", "B", "t2", clicks=50),
            ],
        )
        assert not exp.is_significant

    def test_is_significant_enough_data(self):
        exp = Experiment(
            experiment_id="e1",
            name="Test",
            platform="amazon",
            min_sample_size=100,
            variants=[
                Variant("v0", "A", "t1", clicks=100),
                Variant("v1", "B", "t2", clicks=100),
            ],
        )
        assert exp.is_significant

    def test_to_dict(self):
        exp = Experiment(
            experiment_id="e1",
            name="Test",
            platform="amazon",
            variants=[Variant("v0", "A", "t1")],
        )
        d = exp.to_dict()
        assert d["experiment_id"] == "e1"
        assert d["name"] == "Test"
        assert len(d["variants"]) == 1


class TestSignificanceResult:
    def test_to_dict(self):
        sr = SignificanceResult(
            is_significant=True,
            confidence=0.97,
            z_score=2.17,
            p_value=0.03,
            winner_id="v1",
            loser_id="v0",
            lift=50.0,
            sample_sufficient=True,
        )
        d = sr.to_dict()
        assert d["is_significant"]
        assert d["confidence"] == 0.97
        assert d["winner_id"] == "v1"
        assert d["lift"] == 50.0


class TestCreateExperiment:
    def test_create_basic(self, manager):
        exp = manager.create_experiment(
            name="Test",
            platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "tag-a"},
                {"name": "B", "affiliate_tag": "tag-b"},
            ],
        )
        assert exp.experiment_id
        assert exp.name == "Test"
        assert exp.platform == "amazon"
        assert len(exp.variants) == 2
        assert exp.status == ExperimentStatus.DRAFT

    def test_create_with_weights(self, manager):
        exp = manager.create_experiment(
            name="Weighted",
            platform="shopee",
            variants=[
                {"name": "A", "affiliate_tag": "t1", "traffic_weight": 0.7},
                {"name": "B", "affiliate_tag": "t2", "traffic_weight": 0.3},
            ],
        )
        weights = [v.traffic_weight for v in exp.variants]
        assert abs(sum(weights) - 1.0) < 0.01

    def test_create_three_variants(self, manager):
        exp = manager.create_experiment(
            name="Three Way",
            platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
                {"name": "C", "affiliate_tag": "t3"},
            ],
        )
        assert len(exp.variants) == 3

    def test_create_too_few_variants(self, manager):
        with pytest.raises(ValueError, match="at least 2"):
            manager.create_experiment(
                name="Solo",
                platform="amazon",
                variants=[{"name": "A", "affiliate_tag": "t1"}],
            )

    def test_create_too_many_variants(self, manager):
        with pytest.raises(ValueError, match="Maximum 5"):
            manager.create_experiment(
                name="TooMany",
                platform="amazon",
                variants=[
                    {"name": f"V{i}", "affiliate_tag": f"t{i}"}
                    for i in range(6)
                ],
            )

    def test_create_with_custom_params(self, manager):
        exp = manager.create_experiment(
            name="Custom",
            platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
            confidence_threshold=0.99,
            min_sample_size=500,
            metric="revenue_per_click",
        )
        assert exp.confidence_threshold == 0.99
        assert exp.min_sample_size == 500
        assert exp.metric == "revenue_per_click"


class TestExperimentLifecycle:
    def test_start(self, manager):
        exp = manager.create_experiment(
            name="T", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        assert manager.start_experiment(exp.experiment_id)
        loaded = manager.get_experiment(exp.experiment_id)
        assert loaded.status == ExperimentStatus.RUNNING
        assert loaded.started_at

    def test_pause(self, running_experiment, manager):
        assert manager.pause_experiment(running_experiment.experiment_id)
        loaded = manager.get_experiment(running_experiment.experiment_id)
        assert loaded.status == ExperimentStatus.PAUSED

    def test_resume_paused(self, manager):
        exp = manager.create_experiment(
            name="T", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        manager.start_experiment(exp.experiment_id)
        manager.pause_experiment(exp.experiment_id)
        assert manager.start_experiment(exp.experiment_id)
        loaded = manager.get_experiment(exp.experiment_id)
        assert loaded.status == ExperimentStatus.RUNNING

    def test_complete(self, running_experiment, manager):
        assert manager.complete_experiment(running_experiment.experiment_id, winner_id="v0")
        loaded = manager.get_experiment(running_experiment.experiment_id)
        assert loaded.status == ExperimentStatus.COMPLETED
        assert loaded.winner_variant_id == "v0"

    def test_complete_auto_winner(self, experiment_with_data, manager):
        # Re-fetch to get running status (auto-complete may have triggered)
        loaded = manager.get_experiment(experiment_with_data.experiment_id)
        assert loaded.status in [ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED]

    def test_start_completed_fails(self, manager):
        exp = manager.create_experiment(
            name="T", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        manager.start_experiment(exp.experiment_id)
        manager.complete_experiment(exp.experiment_id)
        assert not manager.start_experiment(exp.experiment_id)

    def test_pause_draft_fails(self, manager):
        exp = manager.create_experiment(
            name="T", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        assert not manager.pause_experiment(exp.experiment_id)


class TestGetAndList:
    def test_get_experiment(self, running_experiment, manager):
        loaded = manager.get_experiment(running_experiment.experiment_id)
        assert loaded is not None
        assert loaded.name == "Amazon Tag Test"
        assert len(loaded.variants) == 2

    def test_get_nonexistent(self, manager):
        assert manager.get_experiment("nonexistent") is None

    def test_list_all(self, manager):
        for i in range(3):
            manager.create_experiment(
                name=f"Test {i}", platform="amazon",
                variants=[
                    {"name": "A", "affiliate_tag": "t1"},
                    {"name": "B", "affiliate_tag": "t2"},
                ],
            )
        exps = manager.list_experiments()
        assert len(exps) == 3

    def test_list_by_status(self, manager):
        exp1 = manager.create_experiment(
            name="Draft", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        exp2 = manager.create_experiment(
            name="Running", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        manager.start_experiment(exp2.experiment_id)

        drafts = manager.list_experiments(status="draft")
        running = manager.list_experiments(status="running")
        assert len(drafts) == 1
        assert len(running) == 1

    def test_delete(self, running_experiment, manager):
        assert manager.delete_experiment(running_experiment.experiment_id)
        assert manager.get_experiment(running_experiment.experiment_id) is None

    def test_delete_nonexistent(self, manager):
        assert not manager.delete_experiment("nonexistent")


class TestVariantAssignment:
    def test_assign_variant(self, running_experiment, manager):
        variant = manager.assign_variant(running_experiment.experiment_id, user_id=12345)
        assert variant is not None
        assert variant.variant_id in ["v0", "v1"]

    def test_consistent_assignment(self, running_experiment, manager):
        """Same user always gets same variant."""
        v1 = manager.assign_variant(running_experiment.experiment_id, user_id=99999)
        v2 = manager.assign_variant(running_experiment.experiment_id, user_id=99999)
        assert v1.variant_id == v2.variant_id

    def test_different_users_different_variants(self, running_experiment, manager):
        """Different users may get different variants (probabilistic)."""
        assignments = set()
        for uid in range(100):
            v = manager.assign_variant(running_experiment.experiment_id, user_id=uid)
            assignments.add(v.variant_id)
        # With 100 users and 50/50 split, very likely both variants assigned
        assert len(assignments) == 2

    def test_assign_draft_returns_none(self, manager):
        exp = manager.create_experiment(
            name="Draft", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        assert manager.assign_variant(exp.experiment_id) is None

    def test_assign_nonexistent(self, manager):
        assert manager.assign_variant("nonexistent") is None

    def test_assign_random_no_user(self, running_experiment, manager):
        variant = manager.assign_variant(running_experiment.experiment_id, user_id=0)
        assert variant is not None


class TestEventRecording:
    def test_record_impression(self, running_experiment, manager):
        manager.record_impression(running_experiment.experiment_id, "v0", user_id=1)
        exp = manager.get_experiment(running_experiment.experiment_id)
        v0 = next(v for v in exp.variants if v.variant_id == "v0")
        assert v0.impressions == 1

    def test_record_click(self, running_experiment, manager):
        manager.record_click(running_experiment.experiment_id, "v0", user_id=1)
        exp = manager.get_experiment(running_experiment.experiment_id)
        v0 = next(v for v in exp.variants if v.variant_id == "v0")
        assert v0.clicks == 1

    def test_record_conversion(self, running_experiment, manager):
        manager.record_conversion(
            running_experiment.experiment_id, "v0", revenue=50.0, user_id=1
        )
        exp = manager.get_experiment(running_experiment.experiment_id)
        v0 = next(v for v in exp.variants if v.variant_id == "v0")
        assert v0.conversions == 1
        assert v0.revenue == 50.0

    def test_multiple_events(self, running_experiment, manager):
        for _ in range(10):
            manager.record_impression(running_experiment.experiment_id, "v0")
            manager.record_click(running_experiment.experiment_id, "v0")
        for _ in range(3):
            manager.record_conversion(running_experiment.experiment_id, "v0", revenue=25.0)

        exp = manager.get_experiment(running_experiment.experiment_id)
        v0 = next(v for v in exp.variants if v.variant_id == "v0")
        assert v0.impressions == 10
        assert v0.clicks == 10
        assert v0.conversions == 3
        assert v0.revenue == 75.0

    def test_events_stored(self, running_experiment, manager):
        manager.record_click(running_experiment.experiment_id, "v0", user_id=42)
        row = manager.conn.execute(
            "SELECT * FROM events WHERE user_id = 42"
        ).fetchone()
        assert row is not None
        assert row["event_type"] == "click"


class TestStatisticalSignificance:
    def test_significance_with_data(self, experiment_with_data, manager):
        sig = manager.check_significance(experiment_with_data.experiment_id)
        assert sig is not None
        assert isinstance(sig, SignificanceResult)
        assert sig.confidence > 0

    def test_significance_identifies_winner(self, experiment_with_data, manager):
        sig = manager.check_significance(experiment_with_data.experiment_id)
        assert sig.winner_id == "v1"  # 15% vs 10%
        assert sig.lift > 0

    def test_significance_with_clear_difference(self, manager):
        exp = manager.create_experiment(
            name="Clear", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
            min_sample_size=50,
        )
        manager.start_experiment(exp.experiment_id)

        # V0: 5% conversion rate
        for _ in range(200):
            manager.record_click(exp.experiment_id, "v0")
        for _ in range(10):
            manager.record_conversion(exp.experiment_id, "v0")

        # V1: 20% conversion rate
        for _ in range(200):
            manager.record_click(exp.experiment_id, "v1")
        for _ in range(40):
            manager.record_conversion(exp.experiment_id, "v1")

        sig = manager.check_significance(exp.experiment_id)
        assert sig.is_significant
        assert sig.winner_id == "v1"
        assert sig.confidence > 0.95

    def test_no_significance_equal_rates(self, manager):
        exp = manager.create_experiment(
            name="Equal", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        manager.start_experiment(exp.experiment_id)

        # Same conversion rate for both
        for _ in range(150):
            manager.record_click(exp.experiment_id, "v0")
            manager.record_click(exp.experiment_id, "v1")
        for _ in range(15):
            manager.record_conversion(exp.experiment_id, "v0")
            manager.record_conversion(exp.experiment_id, "v1")

        sig = manager.check_significance(exp.experiment_id)
        assert not sig.is_significant
        assert sig.lift == 0.0

    def test_significance_no_clicks(self, running_experiment, manager):
        sig = manager.check_significance(running_experiment.experiment_id)
        assert sig is not None
        assert not sig.is_significant
        assert sig.confidence == 0.0

    def test_significance_nonexistent(self, manager):
        assert manager.check_significance("nonexistent") is None

    def test_significance_single_variant(self, manager):
        # Edge case: create experiment then delete a variant
        exp = manager.create_experiment(
            name="T", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        # Delete one variant manually
        manager.conn.execute(
            "DELETE FROM variants WHERE experiment_id = ? AND variant_id = 'v1'",
            (exp.experiment_id,),
        )
        manager.conn.commit()
        assert manager.check_significance(exp.experiment_id) is None

    def test_normal_cdf(self):
        # Standard normal: CDF(0) = 0.5
        assert abs(ABTestManager._normal_cdf(0) - 0.5) < 0.001
        # CDF(-inf) ≈ 0
        assert ABTestManager._normal_cdf(-10) < 0.001
        # CDF(inf) ≈ 1
        assert ABTestManager._normal_cdf(10) > 0.999
        # CDF(1.96) ≈ 0.975
        assert abs(ABTestManager._normal_cdf(1.96) - 0.975) < 0.001


class TestRecommendation:
    def test_recommendation_collect_more(self, running_experiment, manager):
        # Add some data but not enough
        for _ in range(50):
            manager.record_click(running_experiment.experiment_id, "v0")
            manager.record_click(running_experiment.experiment_id, "v1")
        for _ in range(5):
            manager.record_conversion(running_experiment.experiment_id, "v0")
        for _ in range(8):
            manager.record_conversion(running_experiment.experiment_id, "v1")

        rec = manager.get_recommendation(running_experiment.experiment_id)
        assert rec["action"] == "collect_more_data"

    def test_recommendation_not_found(self, manager):
        rec = manager.get_recommendation("nonexistent")
        assert rec["action"] == "not_found"

    def test_recommendation_no_winner(self, manager):
        exp = manager.create_experiment(
            name="Equal", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
            min_sample_size=50,
        )
        manager.start_experiment(exp.experiment_id)
        # Same rates
        for _ in range(100):
            manager.record_click(exp.experiment_id, "v0")
            manager.record_click(exp.experiment_id, "v1")
        for _ in range(10):
            manager.record_conversion(exp.experiment_id, "v0")
            manager.record_conversion(exp.experiment_id, "v1")

        rec = manager.get_recommendation(exp.experiment_id)
        assert rec["action"] == "no_winner_yet"

    def test_recommendation_completed(self, manager):
        exp = manager.create_experiment(
            name="Done", platform="amazon",
            variants=[
                {"name": "A", "affiliate_tag": "t1"},
                {"name": "B", "affiliate_tag": "t2"},
            ],
        )
        manager.start_experiment(exp.experiment_id)
        manager.complete_experiment(exp.experiment_id, winner_id="v0")

        rec = manager.get_recommendation(exp.experiment_id)
        assert rec["action"] == "completed"

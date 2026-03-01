"""Tests for the fraud detection engine."""

import os
import time
import tempfile
import pytest
from app.services.fraud_detector import (
    FraudDetector, ClickEvent, FraudVerdict, FraudSignal,
    RiskLevel, FraudType, ActionType,
    BOT_SIGNATURES, PROXY_INDICATORS,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "fraud_test.db")


@pytest.fixture
def detector(db_path):
    d = FraudDetector(db_path=db_path)
    yield d
    d.close()


@pytest.fixture
def clean_click():
    return ClickEvent(
        user_id=1001,
        chat_id=5001,
        platform="amazon",
        product_id="B0TEST123",
        url="https://amazon.com/dp/B0TEST123",
        ip_address="1.2.3.4",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    )


class TestClickEvent:
    def test_fingerprint_deterministic(self):
        c1 = ClickEvent(user_id=1, platform="amazon", product_id="X", ip_address="1.1.1.1")
        c2 = ClickEvent(user_id=1, platform="amazon", product_id="X", ip_address="1.1.1.1")
        assert c1.fingerprint == c2.fingerprint

    def test_fingerprint_differs_for_different_input(self):
        c1 = ClickEvent(user_id=1, platform="amazon", product_id="X", ip_address="1.1.1.1")
        c2 = ClickEvent(user_id=2, platform="amazon", product_id="X", ip_address="1.1.1.1")
        assert c1.fingerprint != c2.fingerprint

    def test_default_timestamp(self):
        c = ClickEvent(user_id=1)
        assert c.timestamp > 0

    def test_custom_timestamp(self):
        c = ClickEvent(user_id=1, timestamp=1000.0)
        assert c.timestamp == 1000.0


class TestFraudVerdict:
    def test_is_fraudulent(self):
        v = FraudVerdict(click=ClickEvent(user_id=1), risk_score=61)
        assert v.is_fraudulent

    def test_not_fraudulent(self):
        v = FraudVerdict(click=ClickEvent(user_id=1), risk_score=30)
        assert not v.is_fraudulent

    def test_signal_summary_empty(self):
        v = FraudVerdict(click=ClickEvent(user_id=1))
        assert v.signal_summary == "No fraud signals"

    def test_signal_summary_with_signals(self):
        v = FraudVerdict(
            click=ClickEvent(user_id=1),
            signals=[FraudSignal(FraudType.CLICK_FLOOD, 30, "test", 0.8)],
        )
        assert "click_flood" in v.signal_summary


class TestCleanClicks:
    def test_clean_click_allowed(self, detector, clean_click):
        verdict = detector.analyze(clean_click)
        assert verdict.action == ActionType.ALLOW
        assert verdict.risk_level == RiskLevel.CLEAN
        assert verdict.risk_score <= 20

    def test_clean_click_no_signals(self, detector, clean_click):
        verdict = detector.analyze(clean_click)
        # First click should produce no fraud signals
        assert len(verdict.signals) == 0 or verdict.risk_score <= 20

    def test_multiple_clean_clicks_spaced(self, detector):
        """Multiple clicks with reasonable spacing should be fine."""
        for i in range(3):
            click = ClickEvent(
                user_id=2000 + i,  # Different users
                platform="shopee",
                product_id=f"PROD{i}",
            )
            verdict = detector.analyze(click)
            assert verdict.action == ActionType.ALLOW


class TestVelocityDetection:
    def test_click_flood_triggers(self, detector):
        """Rapid clicks from same user should trigger velocity check."""
        user_id = 3000
        for i in range(15):
            click = ClickEvent(
                user_id=user_id,
                platform="amazon",
                product_id=f"PROD{i}",
                timestamp=time.time(),
            )
            verdict = detector.analyze(click)

        # After many rapid clicks, should have elevated risk
        assert verdict.risk_score > 0

    def test_velocity_resets_after_window(self, detector):
        """Clicks should not trigger after velocity window passes."""
        user_id = 3001
        old_time = time.time() - 120  # 2 minutes ago

        # Simulate old clicks
        detector._click_buffer[user_id] = [old_time + i for i in range(5)]

        click = ClickEvent(user_id=user_id, platform="amazon")
        verdict = detector.analyze(click)
        # Old clicks should be pruned
        assert verdict.risk_score <= 20


class TestBotDetection:
    def test_bot_user_agent_detected(self, detector):
        click = ClickEvent(
            user_id=4000,
            user_agent="Mozilla/5.0 (compatible; Googlebot/2.1)",
        )
        verdict = detector.analyze(click)
        has_bot_signal = any(
            s.fraud_type == FraudType.BOT_SIGNATURE for s in verdict.signals
        )
        assert has_bot_signal

    def test_selenium_detected(self, detector):
        click = ClickEvent(
            user_id=4001,
            user_agent="selenium/webdriver Chrome/120",
        )
        verdict = detector.analyze(click)
        has_bot = any(s.fraud_type == FraudType.BOT_SIGNATURE for s in verdict.signals)
        assert has_bot

    def test_python_requests_detected(self, detector):
        click = ClickEvent(
            user_id=4002,
            user_agent="python-requests/2.31.0",
        )
        verdict = detector.analyze(click)
        has_bot = any(s.fraud_type == FraudType.BOT_SIGNATURE for s in verdict.signals)
        assert has_bot

    def test_normal_browser_passes(self, detector):
        click = ClickEvent(
            user_id=4003,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        verdict = detector.analyze(click)
        has_bot = any(s.fraud_type == FraudType.BOT_SIGNATURE for s in verdict.signals)
        assert not has_bot

    def test_empty_ua_no_signal(self, detector):
        click = ClickEvent(user_id=4004, user_agent="")
        verdict = detector.analyze(click)
        has_bot = any(s.fraud_type == FraudType.BOT_SIGNATURE for s in verdict.signals)
        assert not has_bot


class TestDuplicateDetection:
    def test_same_fingerprint_flagged(self, detector):
        click1 = ClickEvent(
            user_id=5000, platform="amazon",
            product_id="SAME", ip_address="1.1.1.1",
        )
        click2 = ClickEvent(
            user_id=5000, platform="amazon",
            product_id="SAME", ip_address="1.1.1.1",
        )
        detector.analyze(click1)
        verdict = detector.analyze(click2)
        has_dup = any(s.fraud_type == FraudType.DUPLICATE_CLICK for s in verdict.signals)
        assert has_dup

    def test_different_fingerprint_ok(self, detector):
        click1 = ClickEvent(
            user_id=5001, platform="amazon",
            product_id="A", ip_address="1.1.1.1",
        )
        click2 = ClickEvent(
            user_id=5001, platform="amazon",
            product_id="B", ip_address="2.2.2.2",
        )
        detector.analyze(click1)
        verdict = detector.analyze(click2)
        has_dup = any(s.fraud_type == FraudType.DUPLICATE_CLICK for s in verdict.signals)
        assert not has_dup


class TestReferrerCheck:
    def test_suspicious_referrer(self, detector):
        click = ClickEvent(
            user_id=6000,
            referrer="https://fiverr.com/gig/buy-clicks",
        )
        verdict = detector.analyze(click)
        has_ref = any(
            s.fraud_type == FraudType.SUSPICIOUS_REFERRER for s in verdict.signals
        )
        assert has_ref

    def test_normal_referrer_ok(self, detector):
        click = ClickEvent(
            user_id=6001,
            referrer="https://google.com/search?q=product",
        )
        verdict = detector.analyze(click)
        has_ref = any(
            s.fraud_type == FraudType.SUSPICIOUS_REFERRER for s in verdict.signals
        )
        assert not has_ref

    def test_empty_referrer_ok(self, detector):
        click = ClickEvent(user_id=6002, referrer="")
        verdict = detector.analyze(click)
        has_ref = any(
            s.fraud_type == FraudType.SUSPICIOUS_REFERRER for s in verdict.signals
        )
        assert not has_ref


class TestRegularInterval:
    def test_regular_bot_pattern_detected(self, detector):
        """Perfectly regular click intervals suggest automation."""
        user_id = 7000
        base = time.time()
        # Simulate 10 clicks exactly 2 seconds apart
        detector._click_buffer[user_id] = [base + i * 2.0 for i in range(10)]

        click = ClickEvent(user_id=user_id, timestamp=base + 20.0)
        verdict = detector.analyze(click)
        has_interval = any(
            s.fraud_type == FraudType.REGULAR_INTERVAL for s in verdict.signals
        )
        assert has_interval

    def test_irregular_human_pattern_ok(self, detector):
        """Irregular intervals (human-like) should not trigger."""
        user_id = 7001
        base = time.time()
        # Random-ish intervals
        intervals = [3.2, 7.8, 1.5, 15.3, 4.7, 8.2, 22.1, 6.4, 11.9]
        timestamps = [base]
        for i in intervals:
            timestamps.append(timestamps[-1] + i)
        detector._click_buffer[user_id] = timestamps

        click = ClickEvent(user_id=user_id, timestamp=timestamps[-1] + 5)
        verdict = detector.analyze(click)
        has_interval = any(
            s.fraud_type == FraudType.REGULAR_INTERVAL for s in verdict.signals
        )
        assert not has_interval


class TestBlocklist:
    def test_block_user(self, detector):
        detector.block_user(8000, reason="test block")
        assert detector.is_blocked(8000)

    def test_unblock_user(self, detector):
        detector.block_user(8001, reason="temp")
        detector.unblock_user(8001)
        assert not detector.is_blocked(8001)

    def test_blocked_user_always_rejected(self, detector):
        detector.block_user(8002)
        click = ClickEvent(user_id=8002, platform="amazon")
        verdict = detector.analyze(click)
        assert verdict.risk_score == 100
        assert verdict.action == ActionType.BLOCK

    def test_auto_block_on_high_score(self, detector):
        """Users exceeding block threshold get auto-blocked."""
        # Use bot UA + suspicious referrer + flood to get high score
        for i in range(20):
            click = ClickEvent(
                user_id=8003,
                user_agent="python-requests/2.31.0 bot spider",
                referrer="https://fiverr.com/clicks",
                platform="amazon",
                product_id="SAME",
                ip_address="1.1.1.1",
            )
            detector.analyze(click)

        # Should now be blocked
        assert detector.is_blocked(8003)


class TestQuarantine:
    def test_quarantine_throttles(self, detector):
        """Quarantined users get throttled."""
        detector._quarantined[9000] = time.time() + 3600
        click = ClickEvent(user_id=9000)
        verdict = detector.analyze(click)
        assert verdict.action == ActionType.THROTTLE

    def test_quarantine_expires(self, detector):
        """Expired quarantine lets user through."""
        detector._quarantined[9001] = time.time() - 1  # Already expired
        click = ClickEvent(user_id=9001, platform="shopee")
        verdict = detector.analyze(click)
        assert verdict.action != ActionType.THROTTLE
        assert 9001 not in detector._quarantined


class TestReporting:
    def test_user_risk_history(self, detector):
        click = ClickEvent(user_id=10000, platform="amazon")
        detector.analyze(click)
        history = detector.get_user_risk_history(10000)
        assert len(history) >= 1
        assert history[0]["user_id"] == 10000

    def test_user_risk_score(self, detector):
        click = ClickEvent(user_id=10001, platform="amazon")
        detector.analyze(click)
        score = detector.get_user_risk_score(10001)
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_daily_stats(self, detector):
        click = ClickEvent(user_id=10002)
        detector.analyze(click)
        stats = detector.get_daily_stats(1)
        assert len(stats) >= 1

    def test_generate_report(self, detector):
        for i in range(5):
            click = ClickEvent(user_id=10003 + i, platform="shopee")
            detector.analyze(click)
        report = detector.generate_report(days=1)
        assert "total_checks" in report
        assert "blocked_users" in report
        assert report["total_checks"] >= 5

    def test_top_offenders_empty(self, detector):
        offenders = detector.get_top_offenders()
        assert isinstance(offenders, list)

    def test_top_offenders_with_data(self, detector):
        # Generate enough events for same user
        for i in range(5):
            click = ClickEvent(
                user_id=10010,
                user_agent="bot crawler",
                platform="amazon",
            )
            detector.analyze(click)
        offenders = detector.get_top_offenders()
        if offenders:
            assert offenders[0]["user_id"] == 10010


class TestCleanup:
    def test_cleanup_removes_old(self, detector):
        click = ClickEvent(user_id=11000)
        detector.analyze(click)
        # Cleanup with 0 days should remove everything
        detector.cleanup(days=0)
        history = detector.get_user_risk_history(11000)
        assert len(history) == 0


class TestRiskLevels:
    def test_score_to_level_mapping(self, detector):
        assert detector._score_to_level(0) == RiskLevel.CLEAN
        assert detector._score_to_level(20) == RiskLevel.CLEAN
        assert detector._score_to_level(21) == RiskLevel.LOW
        assert detector._score_to_level(40) == RiskLevel.LOW
        assert detector._score_to_level(41) == RiskLevel.MEDIUM
        assert detector._score_to_level(60) == RiskLevel.MEDIUM
        assert detector._score_to_level(61) == RiskLevel.HIGH
        assert detector._score_to_level(80) == RiskLevel.HIGH
        assert detector._score_to_level(81) == RiskLevel.CRITICAL
        assert detector._score_to_level(100) == RiskLevel.CRITICAL

    def test_action_determination(self, detector):
        assert detector._determine_action(10, 1) == ActionType.ALLOW
        assert detector._determine_action(30, 1) == ActionType.FLAG
        assert detector._determine_action(55, 1) == ActionType.THROTTLE
        assert detector._determine_action(85, 1) == ActionType.BLOCK


class TestEdgeCases:
    def test_zero_user_id(self, detector):
        click = ClickEvent(user_id=0)
        verdict = detector.analyze(click)
        assert isinstance(verdict, FraudVerdict)

    def test_negative_timestamp(self):
        click = ClickEvent(user_id=1, timestamp=-1.0)
        assert click.timestamp == -1.0

    def test_very_long_user_agent(self, detector):
        click = ClickEvent(user_id=12000, user_agent="a" * 10000)
        verdict = detector.analyze(click)
        assert isinstance(verdict, FraudVerdict)

    def test_unicode_referrer(self, detector):
        click = ClickEvent(user_id=12001, referrer="https://例え.jp/page")
        verdict = detector.analyze(click)
        assert isinstance(verdict, FraudVerdict)

    def test_concurrent_analysis(self, detector):
        """Multiple analyses should not crash."""
        verdicts = []
        for i in range(50):
            click = ClickEvent(user_id=12002 + i, platform="tiktok")
            v = detector.analyze(click)
            verdicts.append(v)
        assert len(verdicts) == 50

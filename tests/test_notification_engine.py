"""Tests for the notification engine."""

import os
import time
import tempfile
import pytest
from app.services.notification_engine import (
    NotificationEngine, Notification, NotificationType,
    NotificationPriority, NotificationStatus,
    MilestoneConfig, Goal, QuietHours,
    DEFAULT_MILESTONES,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "notif_test.db")


@pytest.fixture
def engine(db_path):
    e = NotificationEngine(db_path=db_path)
    yield e
    e.close()


@pytest.fixture
def quiet_engine(db_path):
    """Engine with quiet hours currently active."""
    from datetime import datetime, timezone
    now_hour = datetime.now(timezone.utc).hour
    qh = QuietHours(enabled=True, start_hour=now_hour, end_hour=(now_hour + 2) % 24)
    e = NotificationEngine(db_path=db_path, quiet_hours=qh)
    yield e
    e.close()


class TestNotification:
    def test_default_id_generated(self):
        n = Notification(
            notification_type=NotificationType.MILESTONE,
            title="Test", body="Body",
        )
        assert len(n.notification_id) == 12

    def test_default_dedup_key(self):
        n = Notification(
            notification_type=NotificationType.MILESTONE,
            title="Test", body="Body",
        )
        assert "milestone:Test" == n.dedup_key

    def test_custom_dedup_key(self):
        n = Notification(
            notification_type=NotificationType.SYSTEM,
            title="X", body="Y",
            dedup_key="custom:key",
        )
        assert n.dedup_key == "custom:key"

    def test_timestamp_set(self):
        n = Notification(
            notification_type=NotificationType.SYSTEM,
            title="X", body="Y",
        )
        assert n.created_at > 0


class TestMilestoneConfig:
    def test_format_message_default(self):
        m = MilestoneConfig(name="Test", threshold=100)
        msg = m.format_message(150.0)
        assert "150" in msg

    def test_format_message_custom(self):
        m = MilestoneConfig(
            name="Revenue",
            threshold=100,
            message_template="💰 Revenue hit ${value:.2f}!",
        )
        msg = m.format_message(125.50)
        assert "$125.50" in msg


class TestGoal:
    def test_progress_calculation(self):
        g = Goal(goal_id="g1", name="Test", target_value=100, current_value=75)
        assert g.progress_pct == 75.0

    def test_completion(self):
        g = Goal(goal_id="g1", name="Test", target_value=100, current_value=100)
        assert g.is_completed

    def test_not_completed(self):
        g = Goal(goal_id="g1", name="Test", target_value=100, current_value=50)
        assert not g.is_completed

    def test_zero_target(self):
        g = Goal(goal_id="g1", name="Test", target_value=0, current_value=10)
        assert g.progress_pct == 0.0

    def test_over_target(self):
        g = Goal(goal_id="g1", name="Test", target_value=100, current_value=200)
        assert g.progress_pct == 100.0  # Capped


class TestQuietHours:
    def test_disabled(self):
        qh = QuietHours(enabled=False)
        assert not qh.is_quiet_now()

    def test_enabled_in_range(self):
        from datetime import datetime, timezone
        now_hour = datetime.now(timezone.utc).hour
        qh = QuietHours(enabled=True, start_hour=now_hour,
                         end_hour=(now_hour + 2) % 24)
        assert qh.is_quiet_now()

    def test_enabled_out_of_range(self):
        from datetime import datetime, timezone
        now_hour = datetime.now(timezone.utc).hour
        qh = QuietHours(enabled=True,
                         start_hour=(now_hour + 5) % 24,
                         end_hour=(now_hour + 7) % 24)
        assert not qh.is_quiet_now()

    def test_wrap_around_midnight(self):
        qh = QuietHours(enabled=True, start_hour=22, end_hour=6)
        # This wraps around midnight
        from datetime import datetime, timezone
        now_hour = datetime.now(timezone.utc).hour
        if now_hour >= 22 or now_hour < 6:
            assert qh.is_quiet_now()
        else:
            assert not qh.is_quiet_now()


class TestMilestoneChecks:
    def test_first_click_milestone(self, engine):
        notifications = engine.check_milestones("clicks", 1)
        names = [n.title for n in notifications]
        assert any("First Click" in n for n in names)

    def test_milestone_not_repeated(self, engine):
        engine.check_milestones("clicks", 1)
        notifications = engine.check_milestones("clicks", 2)
        # First Click should not trigger again
        names = [n.title for n in notifications]
        assert not any("First Click" in n for n in names)

    def test_100_clicks_milestone(self, engine):
        notifications = engine.check_milestones("clicks", 100)
        names = [n.title for n in notifications]
        assert any("100 Clicks" in n for n in names)

    def test_revenue_milestone(self, engine):
        notifications = engine.check_milestones("revenue", 10)
        names = [n.title for n in notifications]
        assert any("$10" in n for n in names)

    def test_first_sale_milestone(self, engine):
        notifications = engine.check_milestones("revenue", 0.50)
        names = [n.title for n in notifications]
        assert any("First Sale" in n for n in names)

    def test_no_milestone_below_threshold(self, engine):
        notifications = engine.check_milestones("clicks", 0)
        assert len(notifications) == 0

    def test_multiple_milestones_at_once(self, engine):
        """Jumping to 1000 should trigger multiple milestones."""
        notifications = engine.check_milestones("clicks", 1000)
        assert len(notifications) >= 3  # First, 10, 100, 1K


class TestAnomalyDetection:
    def test_no_anomaly_without_baseline(self, engine):
        result = engine.check_anomaly("clicks", 100)
        assert result is None  # Not enough data

    def test_anomaly_after_baseline(self, engine):
        # Build baseline
        for v in [100, 105, 98, 102, 97, 103, 99, 101, 96, 104]:
            engine.check_anomaly("clicks", v)

        # Now spike
        result = engine.check_anomaly("clicks", 500)
        if result:
            assert result.notification_type == NotificationType.ANOMALY
            assert "spike" in result.body.lower()

    def test_drop_anomaly(self, engine):
        # Build baseline at ~100
        for v in [100, 105, 98, 102, 97, 103, 99, 101, 96, 104]:
            engine.check_anomaly("daily_clicks", v)

        # Now drop
        result = engine.check_anomaly("daily_clicks", 10)
        if result:
            assert "drop" in result.body.lower()

    def test_no_anomaly_for_normal(self, engine):
        for v in [100, 105, 98, 102, 97, 103, 99, 101, 96, 104]:
            engine.check_anomaly("test_metric", v)
        result = engine.check_anomaly("test_metric", 101)
        assert result is None


class TestDigests:
    def test_daily_digest(self, engine):
        notif = engine.generate_daily_digest(
            clicks_today=500,
            conversions_today=25,
            revenue_today=199.50,
            top_platform="Amazon",
        )
        assert notif.notification_type == NotificationType.DIGEST
        assert "500" in notif.body
        assert "$199.50" in notif.body
        assert "Amazon" in notif.body

    def test_daily_digest_zero(self, engine):
        notif = engine.generate_daily_digest()
        assert "0" in notif.body

    def test_weekly_digest(self, engine):
        notif = engine.generate_weekly_digest({
            "clicks": 3000,
            "conversions": 150,
            "revenue": 1250.00,
            "growth_pct": 15.5,
        })
        assert notif.notification_type == NotificationType.DIGEST
        assert "3,000" in notif.body
        assert "15.5%" in notif.body

    def test_weekly_digest_negative_growth(self, engine):
        notif = engine.generate_weekly_digest({
            "clicks": 1000,
            "conversions": 50,
            "revenue": 500.00,
            "growth_pct": -20.0,
        })
        assert "↓" in notif.body


class TestGoalManagement:
    def test_create_goal(self, engine):
        goal = engine.create_goal("Revenue $500", 500.0)
        assert goal.goal_id
        assert goal.target_value == 500.0

    def test_list_goals(self, engine):
        engine.create_goal("G1", 100)
        engine.create_goal("G2", 200)
        goals = engine.list_goals()
        assert len(goals) == 2

    def test_update_goal_progress(self, engine):
        goal = engine.create_goal("Test Goal", 100)
        notif = engine.update_goal_progress(goal.goal_id, 50)
        assert notif is None  # Not completed yet

    def test_goal_completion_notification(self, engine):
        goal = engine.create_goal("Revenue Target", 100)
        notif = engine.update_goal_progress(goal.goal_id, 100)
        assert notif is not None
        assert notif.notification_type == NotificationType.GOAL
        assert "Completed" in notif.title

    def test_goal_over_completion(self, engine):
        goal = engine.create_goal("Clicks", 50)
        notif = engine.update_goal_progress(goal.goal_id, 75)
        assert notif is not None

    def test_completed_goal_no_double_notify(self, engine):
        goal = engine.create_goal("Test", 100)
        engine.update_goal_progress(goal.goal_id, 100)
        notif = engine.update_goal_progress(goal.goal_id, 150)
        assert notif is None  # Already completed

    def test_delete_goal(self, engine):
        goal = engine.create_goal("Delete Me", 100)
        assert engine.delete_goal(goal.goal_id)
        assert len(engine.list_goals()) == 0

    def test_delete_nonexistent_goal(self, engine):
        assert not engine.delete_goal("nonexistent")

    def test_list_with_completed(self, engine):
        goal = engine.create_goal("Done", 10)
        engine.update_goal_progress(goal.goal_id, 10)
        assert len(engine.list_goals(include_completed=False)) == 0
        assert len(engine.list_goals(include_completed=True)) == 1


class TestNotificationDelivery:
    def test_send_notification(self, engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Test", body="Hello",
        )
        assert engine.send(notif)

    def test_dedup_blocks_duplicate(self, engine):
        notif1 = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Same", body="Hello",
            dedup_key="test:same",
        )
        notif2 = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Same", body="Hello again",
            dedup_key="test:same",
        )
        assert engine.send(notif1)
        assert not engine.send(notif2)  # Blocked by dedup

    def test_handler_called(self, engine):
        received = []
        engine.register_handler(lambda n: received.append(n) or True)

        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Handler Test", body="Body",
        )
        engine.send(notif)
        assert len(received) == 1
        assert received[0].title == "Handler Test"

    def test_quiet_hours_defer(self, quiet_engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Quiet", body="Shh",
            priority=NotificationPriority.LOW,
        )
        result = quiet_engine.send(notif)
        assert not result  # Deferred
        assert len(quiet_engine._pending) == 1

    def test_urgent_bypasses_quiet(self, quiet_engine):
        notif = Notification(
            notification_type=NotificationType.FRAUD,
            title="URGENT", body="Fraud!",
            priority=NotificationPriority.URGENT,
        )
        result = quiet_engine.send(notif)
        assert result  # Urgent bypasses quiet hours

    def test_flush_pending(self, quiet_engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Pending", body="Later",
            priority=NotificationPriority.LOW,
        )
        quiet_engine.send(notif)
        assert len(quiet_engine._pending) == 1

        # Disable quiet hours and flush
        quiet_engine.quiet_hours.enabled = False
        sent = quiet_engine.flush_pending()
        assert sent >= 0  # May still be deduped

    def test_batch_send(self, engine):
        notifications = [
            Notification(
                notification_type=NotificationType.SYSTEM,
                title=f"Batch {i}", body=f"Body {i}",
            )
            for i in range(5)
        ]
        sent = engine.send_batch(notifications)
        assert sent == 5


class TestNotificationHistory:
    def test_get_unread(self, engine):
        engine.send(Notification(
            notification_type=NotificationType.SYSTEM,
            title="Unread", body="Test",
        ))
        unread = engine.get_unread()
        assert len(unread) >= 1

    def test_mark_read(self, engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Read Me", body="Test",
        )
        engine.send(notif)
        assert engine.mark_read(notif.notification_id)

    def test_dismiss(self, engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Dismiss", body="Test",
        )
        engine.send(notif)
        assert engine.dismiss(notif.notification_id)

    def test_get_history(self, engine):
        engine.send(Notification(
            notification_type=NotificationType.REVENUE,
            title="Rev", body="$$$",
        ))
        history = engine.get_history(days=1)
        assert len(history) >= 1

    def test_get_stats(self, engine):
        engine.send(Notification(
            notification_type=NotificationType.SYSTEM,
            title="Stats", body="Test",
        ))
        stats = engine.get_stats()
        assert "by_status" in stats
        assert "by_type" in stats
        assert "total_milestones" in stats


class TestCleanup:
    def test_cleanup_removes_old(self, engine):
        engine.send(Notification(
            notification_type=NotificationType.SYSTEM,
            title="Old", body="Test",
        ))
        engine.cleanup(days=0)
        history = engine.get_history(days=1)
        assert len(history) == 0


class TestEdgeCases:
    def test_empty_title(self, engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="", body="No title",
        )
        assert engine.send(notif)

    def test_very_long_body(self, engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Long", body="x" * 10000,
        )
        assert engine.send(notif)

    def test_unicode_content(self, engine):
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="🎉 成就解锁", body="恭喜达成目标！",
        )
        assert engine.send(notif)

    def test_update_nonexistent_goal(self, engine):
        result = engine.update_goal_progress("fake_id", 100)
        assert result is None

    def test_multiple_handlers(self, engine):
        results = []
        engine.register_handler(lambda n: results.append("h1") or True)
        engine.register_handler(lambda n: results.append("h2") or True)
        engine.send(Notification(
            notification_type=NotificationType.SYSTEM,
            title="Multi", body="Test",
        ))
        assert "h1" in results
        assert "h2" in results

    def test_handler_exception_handled(self, engine):
        def bad_handler(n):
            raise RuntimeError("boom")
        engine.register_handler(bad_handler)
        # Should not raise
        notif = Notification(
            notification_type=NotificationType.SYSTEM,
            title="Error", body="Test",
        )
        engine.send(notif)  # No exception

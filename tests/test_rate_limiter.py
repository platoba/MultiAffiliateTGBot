"""Tests for rate limiter."""

from app.services.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_first_request_allowed(self, rate_limiter):
        result = rate_limiter.check(1)
        assert result.allowed
        assert result.remaining >= 0

    def test_within_limit(self):
        # Use high burst to avoid burst limiting
        limiter = RateLimiter(max_per_minute=5, burst=10)
        for _ in range(4):
            result = limiter.check(1)
            assert result.allowed

    def test_exceeds_limit(self):
        limiter = RateLimiter(max_per_minute=5, burst=10)
        for _ in range(5):
            limiter.check(1)
        result = limiter.check(1)
        assert not result.allowed
        assert result.remaining == 0
        assert result.reset_in > 0

    def test_burst_limit(self):
        limiter = RateLimiter(max_per_minute=100, burst=2)
        limiter.check(1)
        limiter.check(1)
        result = limiter.check(1)  # 3rd request within 5s
        assert not result.allowed

    def test_different_users_independent(self, rate_limiter):
        for _ in range(5):
            rate_limiter.check(1)
        # User 1 is rate limited
        assert not rate_limiter.check(1).allowed
        # User 2 is fine
        assert rate_limiter.check(2).allowed

    def test_reset_user(self, rate_limiter):
        for _ in range(5):
            rate_limiter.check(1)
        assert not rate_limiter.check(1).allowed
        rate_limiter.reset(1)
        assert rate_limiter.check(1).allowed

    def test_reset_all(self, rate_limiter):
        rate_limiter.check(1)
        rate_limiter.check(2)
        assert rate_limiter.active_users == 2
        rate_limiter.reset_all()
        assert rate_limiter.active_users == 0

    def test_remaining_count(self):
        limiter = RateLimiter(max_per_minute=3, burst=10)
        r1 = limiter.check(1)
        assert r1.remaining == 2
        r2 = limiter.check(1)
        assert r2.remaining == 1

    def test_active_users(self, rate_limiter):
        assert rate_limiter.active_users == 0
        rate_limiter.check(1)
        assert rate_limiter.active_users == 1
        rate_limiter.check(2)
        assert rate_limiter.active_users == 2

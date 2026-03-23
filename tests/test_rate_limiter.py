"""Tests for RateLimiter class."""
import time

import pytest

from browser.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test RateLimiter delay enforcement."""

    def test_init_with_defaults(self):
        """RateLimiter init with defaults from RateLimitingConfig (2000, 5000)."""
        limiter = RateLimiter()
        assert limiter.min_delay_ms == 2000
        assert limiter.max_delay_ms == 5000

    def test_wait_sleeps_and_updates_last_action_time(self, monkeypatch):
        """wait() sleeps random(min, max) ms and updates _last_action_time."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        limiter = RateLimiter(min_delay_ms=1000, max_delay_ms=1000)
        limiter.wait()

        assert len(sleeps) == 1
        assert 0.9 <= sleeps[0] <= 1.1  # ~1000ms
        assert limiter._last_action_time > 0

    def test_wait_if_needed_sleeps_remaining(self, monkeypatch):
        """wait_if_needed() sleeps remaining time if called immediately after wait()."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        limiter = RateLimiter(min_delay_ms=1000, max_delay_ms=1000)
        limiter.wait()
        # Call immediately — should sleep remaining time
        limiter.wait_if_needed()

        assert len(sleeps) == 2
        # Second sleep should be close to full delay (elapsed ≈ 0)
        assert sleeps[1] >= 0.8

    def test_wait_if_needed_skips_if_enough_time_passed(self, monkeypatch):
        """wait_if_needed() does NOT sleep if enough time has passed."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        limiter = RateLimiter(min_delay_ms=100, max_delay_ms=100)
        # Simulate an action that happened long ago
        limiter._last_action_time = time.monotonic() - 1.0  # 1 second ago
        limiter._last_delay_ms = 100

        limiter.wait_if_needed()

        # Should NOT sleep since 1000ms > 100ms min_delay
        assert len(sleeps) == 0

    def test_from_config_creates_limiter(self):
        """RateLimiter can be initialized from RateLimitingConfig dataclass."""
        from config.config import RateLimitingConfig

        config = RateLimitingConfig(min_delay_ms=3000, max_delay_ms=6000)
        limiter = RateLimiter.from_config(config)
        assert limiter.min_delay_ms == 3000
        assert limiter.max_delay_ms == 6000

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

    def test_init_with_custom_values(self):
        """RateLimiter init with custom delay values."""
        limiter = RateLimiter(min_delay_ms=1000, max_delay_ms=3000)
        assert limiter.min_delay_ms == 1000
        assert limiter.max_delay_ms == 3000

    def test_wait_sleeps(self, monkeypatch):
        """wait() sleeps for a delay within the configured range."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        limiter = RateLimiter(min_delay_ms=1000, max_delay_ms=1000)
        limiter.wait()

        assert len(sleeps) == 1
        assert 0.9 <= sleeps[0] <= 1.1  # ~1000ms

    def test_wait_respects_range(self, monkeypatch):
        """wait() respects the min/max delay range."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        limiter = RateLimiter(min_delay_ms=2000, max_delay_ms=5000)
        limiter.wait()

        assert len(sleeps) == 1
        assert 1.9 <= sleeps[0] <= 5.1  # within range



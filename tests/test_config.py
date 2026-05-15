"""Tests for config data model - TDD RED phase.

These tests define the contract for config/config.py before implementation.
All tests should FAIL with ModuleNotFoundError initially.
"""

import json

import pytest

from config.config import (
    VALID_DURATIONS,
    AppConfig,
    BrowserConfig,
    ListingDefaults,
    RateLimitingConfig,
)

# ── ListingDefaults tests ──────────────────────────────────────────


class TestListingDefaults:
    """Tests for ListingDefaults duration, price rules, and adjustment validation."""

    def test_duration_valid(self):
        """Valid durations are accepted."""
        for duration in VALID_DURATIONS:
            listing = ListingDefaults(duration=duration)
            assert listing.duration == duration

    def test_duration_invalid(self):
        """Invalid duration raises ValueError."""
        with pytest.raises(ValueError, match="duration"):
            ListingDefaults(duration="2h")

    def test_price_rules_valid(self):
        """Valid min/max price range accepted."""
        listing = ListingDefaults(min_price=200, max_price=100_000)
        assert listing.min_price == 200
        assert listing.max_price == 100_000

    def test_price_rules_invalid_range(self):
        """min_price > max_price raises ValueError."""
        with pytest.raises(ValueError, match="price range"):
            ListingDefaults(min_price=5000, max_price=1000)

    def test_price_rules_below_min(self):
        """min_price below 200 raises ValueError."""
        with pytest.raises(ValueError, match="price range"):
            ListingDefaults(min_price=100)

    def test_price_rules_above_max(self):
        """max_price above 15M raises ValueError."""
        with pytest.raises(ValueError, match="price range"):
            ListingDefaults(max_price=20_000_000)

    def test_price_adjustment_type_invalid(self):
        """Invalid adjustment type raises ValueError."""
        with pytest.raises(ValueError, match="price_adjustment_type"):
            ListingDefaults(price_adjustment_type="absolute")

    def test_relist_mode_valid(self):
        """relist_mode 'all' and 'per_listing' are accepted."""
        assert ListingDefaults(relist_mode="all").relist_mode == "all"
        assert ListingDefaults(relist_mode="per_listing").relist_mode == "per_listing"

    def test_relist_mode_invalid(self):
        """Invalid relist_mode raises ValueError."""
        with pytest.raises(ValueError, match="relist_mode"):
            ListingDefaults(relist_mode="auto")


# ── AppConfig tests ────────────────────────────────────────────────


class TestAppConfig:
    """Tests for AppConfig scan interval and rate limiting validation."""

    def test_scan_interval_valid(self):
        """Scan interval of 60 seconds accepted."""
        config = AppConfig(scan_interval_seconds=60)
        assert config.scan_interval_seconds == 60

    def test_scan_interval_too_low(self):
        """Scan interval below 10 raises ValueError."""
        with pytest.raises(ValueError, match="scan_interval_seconds"):
            AppConfig(scan_interval_seconds=5)

    def test_scan_interval_too_high(self):
        """Scan interval above 3600 raises ValueError."""
        with pytest.raises(ValueError, match="scan_interval_seconds"):
            AppConfig(scan_interval_seconds=4000)

    def test_rate_limiting_invalid_order(self):
        """min_delay > max_delay raises ValueError."""
        with pytest.raises(ValueError, match="min_delay_ms"):
            AppConfig(rate_limiting=RateLimitingConfig(min_delay_ms=5000, max_delay_ms=2000))


# ── Round-trip tests ───────────────────────────────────────────────


class TestConfigRoundTrip:
    """Tests for JSON serialization round-trip."""

    def test_round_trip(self):
        """AppConfig survives to_dict → JSON → from_dict round-trip."""
        original = AppConfig(
            browser=BrowserConfig(headless=True, slow_mo=250),
            listing_defaults=ListingDefaults(
                duration="6h",
                price_adjustment_type="fixed",
                price_adjustment_value=100,
                min_price=500,
                max_price=50_000,
            ),
            scan_interval_seconds=120,
            rate_limiting=RateLimitingConfig(min_delay_ms=1000, max_delay_ms=3000),
        )

        json_str = json.dumps(original.to_dict())
        loaded = AppConfig.from_dict(json.loads(json_str))

        assert loaded == original

    def test_round_trip_preserves_prices(self):
        """Custom min_price/max_price survive to_dict → from_dict."""
        original = AppConfig(listing_defaults=ListingDefaults(min_price=500, max_price=50_000))

        data = original.to_dict()
        loaded = AppConfig.from_dict(data)

        assert loaded.listing_defaults.min_price == 500
        assert loaded.listing_defaults.max_price == 50_000

    def test_defaults_created(self):
        """AppConfig() with no args produces valid defaults."""
        config = AppConfig()
        assert config.scan_interval_seconds == 60
        assert config.listing_defaults.relist_mode == "all"
        assert config.listing_defaults.duration == "1h"
        assert config.browser.headless is False


# ── BrowserConfig tests ────────────────────────────────────────────


class TestBrowserConfig:
    """Tests for BrowserConfig defaults."""

    def test_browser_config_defaults(self):
        """BrowserConfig has correct default values."""
        browser = BrowserConfig()
        assert browser.headless is False
        assert browser.slow_mo == 500
        assert browser.viewport_width == 1280
        assert browser.viewport_height == 720


class TestConfigWarningMessage:
    """HI-01 fix: Verify warning messages use correct format."""

    def test_config_warning_uses_correct_format(self):
        """HI-01 fix: logger must use {self.min_delay_ms} in f-string, not %s."""
        import ast

        with open("config/config.py") as f:
            content = f.read()

        # Check that config.py warning messages don't use %s with f-string
        # The correct format is: logger.warning(f"...{var}...")
        # The incorrect format would be: logger.warning(f"...%s...", var)

        # Parse the file to find logger.warning calls
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("warning", "error")
            ):
                for arg in node.args:
                    if isinstance(arg, ast.JoinedStr):  # f-string
                        fstring_content = ast.unparse(arg) if hasattr(ast, "unparse") else str(arg)
                        # Check that it doesn't contain %s pattern (incorrect in f-string)
                        if "%s" in fstring_content:
                            raise AssertionError("Found %s in f-string warning message. Use {} format instead.")

        # Also verify the file doesn't have the specific bug pattern
        # Search for f"...{var}%s..." pattern
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "logger.warning" in line or "logger.error" in line:
                # Check if this line or next has f-string with %s
                for j in range(i, min(i + 3, len(lines))):  # Check current and next 2 lines
                    if "%s" in lines[j] and "{" in lines[j] and "}" in lines[j]:
                        # This might be the bug pattern
                        raise AssertionError(f"Line {j + 1} may have incorrect format: mixes f-string {{}} with %s")

    def test_rate_limiter_warning_format(self):
        """Verify rate_limiter.py also uses correct warning format (HI-01 fix)."""
        with open("browser/rate_limiter.py") as f:
            content = f.read()

        # The bug was: f"[RateLimiter] Usa valori aggressivi: min_delay_ms=%sms..."
        # The fix is: f"[RateLimiter] Usa valori aggressivi: min_delay_ms={self.min_delay_ms}ms..."

        # Verify the fix is in place
        assert "min_delay_ms={self.min_delay_ms}" in content or "min_delay_ms=%s" not in content, (
            "rate_limiter.py should use {self.min_delay_ms} in f-string, not %s"
        )

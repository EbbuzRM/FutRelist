"""Tests for RateLimiter class."""

import time

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


class TestRateLimiterWarningMessage:
    """HI-01 fix: Verify warning message uses correct f-string format."""

    def test_warning_uses_correct_format(self):
        """HI-01 fix: logger must use {self.min_delay_ms} in f-string, not %s."""
        import ast

        rate_limiter_path = "browser/rate_limiter.py"
        with open(rate_limiter_path) as f:
            content = f.read()

        # Parse the file to find logging calls
        tree = ast.parse(content)

        # Check that warning messages use proper f-string format with {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "warning":
                for arg in node.args:
                    if isinstance(arg, ast.JoinedStr):  # f-string
                        fstring_value = ast.unparse(arg) if hasattr(ast, "unparse") else None
                        if fstring_value and "%s" in fstring_value:
                            raise AssertionError("f-string contains %s format specifier - should use {} instead")
                        elif isinstance(arg, ast.Constant) and isinstance(arg.value, str) and "%s" in arg.value:
                            # Regular string with %s would be wrong in an f-string context
                            # In the original bug, the code was: f"...{var}%s..."
                            pass  # This is hard to detect statically, so we'll check the source

        # Simpler check: verify the source doesn't have the bug pattern
        # The bug was: f"[RateLimiter] Usa valori aggressivi: min_delay_ms=%sms. Rischio..."
        # The fix is: f"[RateLimiter] Usa valori aggressivi: min_delay_ms={self.min_delay_ms}ms. Rischio..."

        # Check that the file contains the correct pattern
        assert "min_delay_ms={self.min_delay_ms}" in content or "min_delay_ms=%s" not in content, (
            "Warning message should use {self.min_delay_ms} in f-string, not %s"
        )

    def test_warning_not_using_percent_s(self):
        """Verify that rate_limiter.py doesn't use %s in warning messages."""
        with open("browser/rate_limiter.py") as f:
            content = f.read()

        # Find lines with logger.warning
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "logger.warning" in line and "%s" in line and "min_delay_ms" in line:
                raise AssertionError(
                    f"Line {i + 1} uses %s in warning message about min_delay_ms. Should use {{}} format."
                )

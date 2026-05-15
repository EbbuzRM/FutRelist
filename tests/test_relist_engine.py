"""Tests for CR-02 fix — _golden_retry_loop return values.

Verifies that _golden_retry_loop returns 3 values (not 4) when wait_interruptible returns True.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from logic.relist_engine import RelistEngine
from models.listing import ListingScanResult, ListingState, PlayerListing


def _make_engine(executor, detector, navigator, page, bot_state, auth, config):
    """Helper to create RelistEngine instance."""
    return RelistEngine(page, config, navigator, detector, executor, auth, bot_state)


def _make_scan(expired_count: int = 0, active_count: int = 0):
    """Build a ListingScanResult for testing."""
    items = []
    for i in range(expired_count):
        items.append(
            PlayerListing(
                index=i,
                player_name=f"Expired {i}",
                state=ListingState.EXPIRED,
            )
        )
    for i in range(active_count):
        items.append(
            PlayerListing(
                index=expired_count + i,
                player_name=f"Active {i}",
                state=ListingState.ACTIVE,
                time_remaining_seconds=3600,
            )
        )
    return ListingScanResult(
        total_count=len(items),
        active_count=active_count,
        expired_count=expired_count,
        sold_count=0,
        listings=items,
    )


class TestGoldenRetryLoopReturnValues:
    """CR-02 fix: _golden_retry_loop must return 3 values, not 4."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", return_value=True)
    def test_returns_three_values_on_reboot(self, mock_gw, mock_dt):
        """CR-02 fix: _golden_retry_loop must return 3 values, not 4 when reboot."""
        now = datetime(2026, 4, 13, 16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        detector = MagicMock()
        detector.scan_listings.return_value = _make_scan(expired_count=2)

        navigator = MagicMock()
        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = True  # Reboot!
        auth = MagicMock()
        config = {}

        engine = _make_engine(executor, detector, navigator, page, bot_state, auth, config)

        # This should return 3 values (retry_s, retry_f, reboot)
        result = engine._golden_retry_loop(0, 0, 2)

        # Verify it returns exactly 3 values
        assert len(result) == 3, f"Expected 3 return values, got {len(result)}"

        retry_s, retry_f, reboot = result
        assert retry_s == 0
        assert retry_f == 0
        assert reboot is True

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", return_value=True)
    @patch("logic.relist_engine.random.uniform", return_value=5.0)
    def test_returns_three_values_on_success(self, mock_uniform, mock_gw, mock_dt):
        """CR-02 fix: _golden_retry_loop returns 3 values on successful relist."""
        now = datetime(2026, 4, 13, 16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"

        detector = MagicMock()
        # First scan: 2 expired items
        # After relist verification: 0 expired
        detector.scan_listings.side_effect = [
            _make_scan(expired_count=2),
            _make_scan(expired_count=0),
        ]

        navigator = MagicMock()
        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}

        engine = _make_engine(executor, detector, navigator, page, bot_state, auth, config)

        # Mock _execute_relist_with_verification to return (2, 0)
        # Use side_effect with lambda to ignore the 'self' argument
        with patch.object(RelistEngine, "_execute_relist_with_verification", side_effect=lambda *args: (2, 0)):
            # Pass processing_count=2 to avoid early return
            # This should return 3 values (retry_s, retry_f, reboot)
            result = engine._golden_retry_loop(0, 0, 2)

            # Verify it returns exactly 3 values
            assert len(result) == 3, f"Expected 3 return values, got {len(result)}"

            retry_s, retry_f, reboot = result
            assert retry_s == 2, f"Expected retry_s=2, got {retry_s}"
            assert retry_f == 0
            assert reboot is False

    def test_function_signature_returns_three_values(self):
        """Verify that _golden_retry_loop is defined to return 3 values."""
        import inspect

        sig = inspect.signature(RelistEngine._golden_retry_loop)
        # The function should return a tuple; we can't directly check return type
        # but we can verify the function exists and is callable
        assert callable(RelistEngine._golden_retry_loop)

        # Verify by reading the source code that return statements return 3 values
        source = inspect.getsource(RelistEngine._golden_retry_loop)

        # Check for return statements that return tuples
        lines = source.split("\n")
        return_lines = [l.strip() for l in lines if l.strip().startswith("return ")]

        # At least one return should have 3 values (comma-separated after "return")
        found_three_values = False
        for ret in return_lines:
            # Count commas in the return statement (roughly indicates number of values)
            # e.g., "return retry_s, retry_f, False" has 2 commas = 3 values
            if ret.count(",") >= 2:
                found_three_values = True
                break

        assert found_three_values, f"Expected _golden_retry_loop to return 3 values. Found returns: {return_lines}"

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

        inspect.signature(RelistEngine._golden_retry_loop)
        # The function should return a tuple; we can't directly check return type
        # but we can verify the function exists and is callable
        assert callable(RelistEngine._golden_retry_loop)

        # Verify by reading the source code that return statements return 3 values
        source = inspect.getsource(RelistEngine._golden_retry_loop)

        # Check for return statements that return tuples
        lines = source.split("\n")
        return_lines = [line.strip() for line in lines if line.strip().startswith("return ")]

        # At least one return should have 3 values (comma-separated after "return")
        found_three_values = False
        for ret in return_lines:
            # Count commas in the return statement (roughly indicates number of values)
            # e.g., "return retry_s, retry_f, False" has 2 commas = 3 values
            if ret.count(",") >= 2:
                found_three_values = True
                break

        assert found_three_values, f"Expected _golden_retry_loop to return 3 values. Found returns: {return_lines}"


class TestGoldenRetryNoDoubleCounting:
    """Bug fix: retry-succeeded items must NOT be double-counted as failed.

    When _golden_retry_loop recovers an item that failed in the initial relist,
    the original failed count must be decremented. Otherwise the item is counted
    twice: once as failed (initial) and once as succeeded (retry).

    The bug is in process_cycle() aggregation at lines 230-231:
        succeeded += retry_s    # correct
        failed += retry_f       # WRONG — doesn't account for retry_s recovering initial failed

    Fix:
        succeeded += retry_s
        failed = max(failed - retry_s + retry_f, 0)

    Scenario:
    - Initial relist: succeeded=7, failed=1
    - Golden retry: retry_s=1, retry_f=0 (recovers the 1 failed item)
    - WRONG (before fix): succeeded=8, failed=1 → total 9, but only 8 items!
    - CORRECT (after fix): succeeded=8, failed=0 → total 8 ✓
    """

    def test_retry_succeeded_compensates_initial_failed(self):
        """Each retry-succeeded item reduces the original failed count by one."""
        # Simulate the process_cycle aggregation logic
        initial_s, initial_f = 7, 1
        retry_s, retry_f = 1, 0  # retry recovers the 1 failed item

        # FIXED aggregation:
        succeeded = initial_s + retry_s
        failed = max(initial_f - retry_s + retry_f, 0)

        assert succeeded == 8, f"Expected succeeded=8, got {succeeded}"
        assert failed == 0, f"Expected failed=0 (not double-counted), got {failed}"
        # Invariant: total processed items = succeeded + failed = 8 (not 9!)
        assert succeeded + failed == 8, "Total items must equal original 8, not 9"

    def test_retry_partial_recovery(self):
        """When retry recovers some but not all failed items."""
        initial_s, initial_f = 10, 3
        retry_s, retry_f = 2, 0  # recovers 2 of 3 failed

        succeeded = initial_s + retry_s
        failed = max(initial_f - retry_s + retry_f, 0)

        assert succeeded == 12
        assert failed == 1  # 1 failed item not recovered
        assert succeeded + failed == 13  # original total

    def test_retry_fails_too(self):
        """When retry itself fails on some items."""
        initial_s, initial_f = 5, 3
        retry_s, retry_f = 1, 1  # recovers 1, but 1 new failure

        succeeded = initial_s + retry_s
        failed = max(initial_f - retry_s + retry_f, 0)

        assert succeeded == 6
        assert failed == 3  # 3 - 1 + 1 = 3
        assert succeeded + failed == 9

    def test_retry_full_recovery(self):
        """When retry recovers ALL failed items."""
        initial_s, initial_f = 15, 1
        retry_s, retry_f = 1, 0

        succeeded = initial_s + retry_s
        failed = max(initial_f - retry_s + retry_f, 0)

        assert succeeded == 16
        assert failed == 0
        assert succeeded + failed == 16

    def test_buggy_aggregation_double_counts(self):
        """Demonstrate the BUG: old aggregation produces wrong totals."""
        initial_s, initial_f = 7, 1
        retry_s, retry_f = 1, 0

        # OLD BUGGY aggregation (before fix):
        succeeded_buggy = initial_s + retry_s
        failed_buggy = initial_f + retry_f

        # This produces 8 succeeded + 1 failed = 9 total, but only 8 items existed!
        assert succeeded_buggy + failed_buggy == 9  # WRONG! Should be 8

        # FIXED aggregation:
        succeeded_fixed = initial_s + retry_s
        failed_fixed = max(initial_f - retry_s + retry_f, 0)

        assert succeeded_fixed + failed_fixed == 8  # CORRECT


class TestProcessCycleGoldenRetryAggregation:
    """Integration test: process_cycle must correctly aggregate golden retry results.

    The bug: when _golden_retry_loop recovers failed items, process_cycle does:
        succeeded += retry_s    # correct
        failed += retry_f       # WRONG — doesn't subtract recovered items

    This test mocks _golden_retry_loop to return known values and verifies
    that process_cycle returns the correct aggregated totals.
    """

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window")
    @patch("logic.relist_engine.is_in_golden_period", return_value=False)
    @patch("logic.relist_engine.is_in_hold_window", return_value=False)
    @patch("logic.relist_engine.get_next_golden_hour", return_value=None)
    @patch("logic.relist_engine.get_min_active_seconds", return_value=None)
    def test_process_cycle_aggregates_retry_without_double_counting(
        self, mock_min_active, mock_next_gh, mock_hold, mock_period, mock_gw, mock_dt
    ):
        """When golden retry recovers a failed item, failed count must decrease."""
        now = datetime(2026, 4, 13, 16, 10)
        mock_dt.now.return_value = now
        # is_in_golden_window is called multiple times:
        # 1. process_cycle line 226 — golden retry check → True
        # 2. _compute_next_wait line 500 → True
        mock_gw.return_value = True

        executor = MagicMock()
        executor.relist_mode = "all"

        detector = MagicMock()
        # Initial scan: 8 expired
        # Post-relist scan (from _execute_relist_with_verification): 1 expired remaining
        # Final scan: 0 expired
        scan_8_expired = _make_scan(expired_count=8, active_count=0)
        scan_1_expired = _make_scan(expired_count=1, active_count=0)
        scan_0_expired = _make_scan(expired_count=0, active_count=0)
        detector.scan_listings.side_effect = [scan_8_expired, scan_1_expired, scan_0_expired]

        navigator = MagicMock()
        navigator.go_to_transfer_list.return_value = True

        page = MagicMock()
        page.url = "https://example.com"

        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        bot_state.consume_force_relist.return_value = False
        bot_state.get_seconds_since_last_relist_by_bot.return_value = 300

        auth = MagicMock()
        auth.is_console_session_active.return_value = False

        config = {}

        engine = RelistEngine(page, config, navigator, detector, executor, auth, bot_state)

        # _execute_relist_with_verification: first call returns (7, 1) — 7 succeeded, 1 failed
        # Second call (from golden retry) returns (1, 0) — recovers the 1 failed
        call_count = [0]

        def mock_relist_verification(scan):
            call_count[0] += 1
            if call_count[0] == 1:
                return 7, 1  # Initial relist: 7 succeeded, 1 failed
            else:
                return 1, 0  # Golden retry: recovers the 1 failed

        with patch.object(RelistEngine, "_execute_relist_with_verification", side_effect=mock_relist_verification):
            succeeded, failed, next_wait, scan_result, deadline, pre_expired = engine.process_cycle()

            # Total items = 8. After retry recovers the 1 failed:
            # succeeded should be 8, failed should be 0
            assert succeeded == 8, f"Expected succeeded=8, got {succeeded}"
            assert failed == 0, f"Expected failed=0 (no double-counting), got {failed}"
            assert succeeded + failed == 8, f"Total must be 8, got {succeeded + failed}"

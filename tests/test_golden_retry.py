"""Unit tests for _golden_retry_relist helper function.

Verifies the retry loop logic for Processing items during golden hours:
- No retry outside golden window
- Retry with fresh scans until all items are relisted
- Exit on golden window close, reboot, navigation failure, or session loss
- Correct wait timing (5-10s random, interruptible)
- Both "all" and "per_listing" relist modes
"""
from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from logic.relist_engine import RelistEngine
from logic.golden_hour import is_in_golden_window
from models.listing import ListingState, PlayerListing, ListingScanResult
from bot_state import RebootRequestError



def _run_golden_retry_relist_helper(executor, detector, navigator, page, bot_state, auth, config, fifa_logger, initial_succeeded=0, initial_failed=0, processing_count=0):
    engine = RelistEngine(page, config, navigator, detector, executor, auth, bot_state)
    try:
        retry_s, retry_f, reboot = engine._golden_retry_loop(initial_succeeded, initial_failed, processing_count)
        return retry_s, retry_f, reboot
    except RebootRequestError:
        return 0, 0, True

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BASE_DATE = (2026, 4, 13)


def dt(hour: int, minute: int, second: int = 0) -> datetime:
    """Shorthand to build a datetime on the base date."""
    return datetime(*BASE_DATE, hour=hour, minute=minute, second=second)


def _make_scan(expired_count: int = 0, active_count: int = 0,
               listings: list[PlayerListing] | None = None) -> ListingScanResult:
    """Build a ListingScanResult for testing."""
    if listings is not None:
        ec = sum(1 for l in listings if l.state in (ListingState.EXPIRED, ListingState.PROCESSING))
        ac = sum(1 for l in listings if l.state == ListingState.ACTIVE)
        return ListingScanResult(
            total_count=len(listings), active_count=ac, expired_count=ec,
            sold_count=0, listings=listings,
        )
    items = []
    for i in range(expired_count):
        items.append(PlayerListing(
            index=i, player_name=f"Expired {i}", state=ListingState.EXPIRED,
        ))
    for i in range(active_count):
        items.append(PlayerListing(
            index=expired_count + i, player_name=f"Active {i}", state=ListingState.ACTIVE,
            time_remaining_seconds=3600,
        ))
    return ListingScanResult(
        total_count=len(items), active_count=active_count,
        expired_count=expired_count, sold_count=0, listings=items,
    )


def _make_batch_result(succeeded: int = 0, failed: int = 0, relist_error: str | None = None):
    """Build a mock RelistBatchResult."""
    result = MagicMock()
    result.succeeded = succeeded
    result.total = succeeded + failed
    result.relist_error = relist_error
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoRetryOutsideGoldenWindow:
    """Helper returns (0, 0, False) when NOT in golden window."""

    @patch("logic.relist_engine.is_in_golden_window", return_value=False)
    def test_no_retry_at_14_00(self, mock_gw):
        """At 14:00, function returns (0, 0) immediately — no loop entered."""
        executor = MagicMock()
        detector = MagicMock()
        navigator = MagicMock()
        page = MagicMock()
        bot_state = MagicMock()
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        result = _run_golden_retry_relist_helper(
            executor=executor, detector=detector, navigator=navigator,
            page=page, bot_state=bot_state, auth=auth, config=config,
            fifa_logger=fifa_logger,
        )

        assert result == (0, 0, False)
        detector.scan_listings.assert_not_called()
        executor.relist_all.assert_not_called()


class TestSingleRetryClearsAll:
    """At golden window, first scan has expired, second scan has 0 expired → done."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=7.0)
    def test_single_retry(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"
        executor.relist_all.return_value = _make_batch_result(succeeded=3)

        detector = MagicMock()
        detector.scan_listings.side_effect = [
            _make_scan(expired_count=3),
            _make_scan(expired_count=0),
            _make_scan(expired_count=0),  # re-scan after post-relist verification
        ]

        navigator = MagicMock()
        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=navigator,
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, initial_succeeded=3, initial_failed=0,
                processing_count=3,
            )

        assert succeeded == 3
        assert failed == 0
        assert should_continue is False
        executor.relist_all.assert_called_once()


class TestMultipleRetriesNeeded:
    """At golden window, scan sequence: 5 expired → 3 expired → 0 expired."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True, True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=6.0)
    def test_multiple_retries(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"
        executor.relist_all.side_effect = [
            _make_batch_result(succeeded=5),
            _make_batch_result(succeeded=3),
        ]

        detector = MagicMock()
        # Each iteration: fresh scan → relist → post-relist verification scan
        # Iter 1: 5 expired → relist → 3 still in Processing (not "failed")
        # Iter 2: 3 expired → relist → 0 expired
        # Iter 3: 0 expired → break
        processing_3 = [
            PlayerListing(index=i, player_name=f"Processing {i}", state=ListingState.PROCESSING)
            for i in range(3)
        ]
        active_2 = [
            PlayerListing(index=3+i, player_name=f"Active {i}", state=ListingState.ACTIVE,
                          time_remaining_seconds=3600)
            for i in range(2)
        ]
        post_scan_1 = _make_scan(listings=processing_3 + active_2)
        detector.scan_listings.side_effect = [
            _make_scan(expired_count=5),     # iter 1: fresh scan
            post_scan_1,                     # iter 1: post-relist (3 Processing, not "failed")
            _make_scan(expired_count=3),     # iter 2: fresh scan
            _make_scan(expired_count=0),     # iter 2: post-relist
            _make_scan(expired_count=0),     # iter 3: fresh scan → break
        ]

        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, processing_count=5,
            )

        assert succeeded == 2 + 3  # 5 total (2 confirmed active + 3 Processing that become expired in iter 2)
        assert failed == 0
        assert should_continue is False


class TestGoldenWindowClosesMidRetry:
    """Golden window closes during retry — exits with whatever was relisted."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, False])
    @patch("logic.relist_engine.random.uniform", return_value=5.5)
    def test_window_closes(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"
        executor.relist_all.return_value = _make_batch_result(succeeded=2)

        detector = MagicMock()
        detector.scan_listings.side_effect = [
            _make_scan(expired_count=2),     # fresh scan
            _make_scan(expired_count=0),     # post-relist verification
        ]

        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, processing_count=2,
            )

        # Got 2 relisted before window closed
        assert succeeded == 2
        assert failed == 0
        assert should_continue is False


class TestRebootInterruptsWait:
    """wait_interruptible signals reboot — function returns immediately."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True])
    @patch("logic.relist_engine.random.uniform", return_value=8.0)
    def test_reboot_during_wait(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"

        detector = MagicMock()
        page = MagicMock()

        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = True  # Reboot!

        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        succeeded, failed, should_continue = _run_golden_retry_relist_helper(
            executor=executor, detector=detector, navigator=MagicMock(),
            page=page, bot_state=bot_state, auth=auth, config=config,
            fifa_logger=fifa_logger, processing_count=1,
        )

        assert succeeded == 0
        assert failed == 0
        assert should_continue is True
        detector.scan_listings.assert_not_called()
        executor.relist_all.assert_not_called()


class TestNavigationFailureStopsRetry:
    """navigate_with_retry returns False → stops retrying."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=6.5)
    def test_navigation_failure(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"

        detector = MagicMock()
        page = MagicMock()

        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False

        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=False):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger,
            )

        assert succeeded == 0
        assert failed == 0
        assert should_continue is False
        detector.scan_listings.assert_not_called()


class TestPerListingModeUsesRelistSingle:
    """When executor.relist_mode == "per_listing", uses the per-listing path."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=7.5)
    def test_per_listing_mode(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "per_listing"

        expired_items = [
            PlayerListing(index=0, player_name="Player A", state=ListingState.EXPIRED),
            PlayerListing(index=1, player_name="Player B", state=ListingState.PROCESSING),
        ]
        first_scan = _make_scan(listings=expired_items + [
            PlayerListing(index=2, player_name="Player C", state=ListingState.ACTIVE,
                          time_remaining_seconds=3600),
        ])
        second_scan = _make_scan(expired_count=0, active_count=3)

        detector = MagicMock()
        detector.scan_listings.side_effect = [first_scan, second_scan]

        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True), \
             patch.object(RelistEngine, "_execute_relist_with_verification", return_value=(2, 0)):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, processing_count=2,
            )

        assert succeeded == 2
        assert failed == 0
        assert should_continue is False
        executor.relist_all.assert_not_called()


class TestSessionRecoveryOnInvalidSession:
    """When session recovery returns True (needs continue), exit retry loop."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=6.0)
    def test_session_recovery_triggers_exit(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"
        batch = _make_batch_result(succeeded=0, failed=2, relist_error="Session expired")
        executor.relist_all.return_value = batch

        detector = MagicMock()
        detector.scan_listings.return_value = _make_scan(expired_count=2)

        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True), \
             patch.object(RelistEngine, "_handle_session_recovery", return_value=True), \
             patch.object(RelistEngine, "_save_error_screenshot"):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, processing_count=2,
            )

        assert should_continue is True


class TestWaitTiming:
    """Verify the retry wait uses random.uniform(5, 10) and passes to wait_interruptible."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=8.3)
    def test_wait_uses_random_uniform(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"
        executor.relist_all.return_value = _make_batch_result(succeeded=1)

        detector = MagicMock()
        detector.scan_listings.side_effect = [
            _make_scan(expired_count=1),
            _make_scan(expired_count=0),
            _make_scan(expired_count=0),
        ]

        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, processing_count=5,
            )

        mock_uniform.assert_called_with(5, 10)
        bot_state.wait_interruptible.assert_called_with(8.3)


class TestFreshScanEachRetry:
    """Verify that each retry does a FRESH scan (detector.scan_listings called)."""

    @patch("logic.relist_engine.datetime")
    @patch("logic.relist_engine.is_in_golden_window", side_effect=[True, True, True, True, True, True, True, True])
    @patch("logic.relist_engine.random.uniform", return_value=5.0)
    def test_fresh_scan_each_iteration(self, mock_uniform, mock_gw, mock_dt):
        now = dt(16, 10)
        mock_dt.now.return_value = now

        executor = MagicMock()
        executor.relist_mode = "all"
        executor.relist_all.side_effect = [
            _make_batch_result(succeeded=2),
            _make_batch_result(succeeded=1),
            _make_batch_result(succeeded=1),
        ]

        detector = MagicMock()
        # Each iteration: fresh scan + post-relist scan = 2 calls per iteration
        # 3 iterations: iter1 (2 expired → relist → 1 processing), iter2 (1 expired → relist → 0), iter3 (0 → break)
        processing_1 = [
            PlayerListing(index=0, player_name="Processing 0", state=ListingState.PROCESSING),
        ]
        active_1 = [
            PlayerListing(index=1, player_name="Active 0", state=ListingState.ACTIVE,
                          time_remaining_seconds=3600),
        ]
        post_scan_1 = _make_scan(listings=processing_1 + active_1)
        detector.scan_listings.side_effect = [
            _make_scan(expired_count=2),     # iter 1: fresh scan
            post_scan_1,                     # iter 1: post-relist (1 Processing, not "failed")
            _make_scan(expired_count=1),     # iter 2: fresh scan
            _make_scan(expired_count=0),     # iter 2: post-relist
            _make_scan(expired_count=0),     # iter 3: fresh scan → break
        ]

        page = MagicMock()
        bot_state = MagicMock()
        bot_state.wait_interruptible.return_value = False
        auth = MagicMock()
        config = {}
        fifa_logger = logging.getLogger("test")

        with patch.object(RelistEngine, "_navigate_with_retry", return_value=True):
            succeeded, failed, should_continue = _run_golden_retry_relist_helper(
                executor=executor, detector=detector, navigator=MagicMock(),
                page=page, bot_state=bot_state, auth=auth, config=config,
                fifa_logger=fifa_logger, processing_count=2,
            )

        assert detector.scan_listings.call_count == 5
        assert succeeded == 1 + 1  # 2 total (1 confirmed active + 1 Processing that became expired)
        assert should_continue is False

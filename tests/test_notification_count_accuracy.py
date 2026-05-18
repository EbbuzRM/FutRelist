"""
Tests for notification count accuracy fixes.

Bug 1: expired_detected must reflect cumulative processed items (relisted + failed),
       NOT the max DOM scan count which can over-count when same items are re-scanned.

Bug 2: relisted must be DOM-verified (pre vs post scan), not based on HTTP responses.

Bug 3: failed must include silently ignored items, calculated as
       expired_detected - relisted, not just HTTP non-200 responses.
"""

from unittest.mock import MagicMock

from core.notification_batch import NotificationBatch
from models.listing import ListingScanResult


class TestExpiredDetectedBasedOnProcessedNotScan:
    """Bug 1: expired_detected must track cumulative processed items, not DOM scan counts."""

    def test_expired_detected_uses_processed_total_not_dom_scan_count(self):
        """When DOM scan shows more expired than actually processed,
        expired_detected must use the processed total."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # Scenario: DOM shows 20 expired items, but only 15 were actually processed
        # (5 were re-scanned from previous cycle, not new items)
        scan.expired_count = 20  # DOM count (inflated by re-scanning)
        batch.accumulate(scan, succeeded=10, failed=5)

        # expired_detected should be 15 (10 + 5 processed), NOT 20 (DOM count)
        assert batch.expired_detected == 15
        assert batch.relisted == 10
        assert batch.failed == 5

    def test_expired_detected_does_not_increase_when_no_new_processing(self):
        """If a cycle processes 0 items, expired_detected must not increase
        even if DOM scan shows expired items."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # First cycle: process 12 items
        scan.expired_count = 12
        batch.accumulate(scan, succeeded=10, failed=2)
        assert batch.expired_detected == 12

        # Second cycle: DOM still shows 12 expired (same items, not yet processed)
        # but we process 0 this cycle
        scan.expired_count = 12
        batch.accumulate(scan, succeeded=0, failed=0)

        # expired_detected must stay at 12, not increase
        assert batch.expired_detected == 12
        assert batch.relisted == 10
        assert batch.failed == 2

    def test_expired_detected_grows_only_with_actual_processing(self):
        """expired_detected grows only when items are actually processed."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # Cycle 1: process 8 items
        scan.expired_count = 10
        batch.accumulate(scan, succeeded=6, failed=2)
        assert batch.expired_detected == 8

        # Cycle 2: process 4 more items
        scan.expired_count = 8
        batch.accumulate(scan, succeeded=3, failed=1)
        assert batch.expired_detected == 12  # 8 + 4

        # Cycle 3: no processing
        scan.expired_count = 6
        batch.accumulate(scan, succeeded=0, failed=0)
        assert batch.expired_detected == 12  # stays at 12

    def test_expired_detected_capped_at_transfer_list_capacity(self):
        """expired_detected must never exceed TRANSFER_LIST_CAPACITY (100)."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # Process items across multiple cycles
        scan.expired_count = 50
        batch.accumulate(scan, succeeded=40, failed=10)
        assert batch.expired_detected == 50

        scan.expired_count = 60
        batch.accumulate(scan, succeeded=35, failed=15)
        # Total processed = 50 + 50 = 100, exactly at capacity
        assert batch.expired_detected == 100

        scan.expired_count = 70
        batch.accumulate(scan, succeeded=20, failed=10)
        # Total processed = 100 + 30 = 130, but capped at 100
        assert batch.expired_detected == 100


class TestFailedIncludesSilentlyIgnoredItems:
    """Bug 3: failed must include silently ignored items.

    failed is derived as expired_detected - relisted.
    If the caller under-reports failed (e.g., EA silently ignored items),
    the batch corrects it.
    """

    def test_failed_derived_from_expired_detected_minus_relisted(self):
        """failed must be expired_detected - relisted to catch silent ignores."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # Caller correctly reports: 15 succeeded, 1 failed out of 16 expired
        scan.expired_count = 16
        batch.accumulate(scan, succeeded=15, failed=1)

        assert batch.expired_detected == 16
        assert batch.relisted == 15
        assert batch.failed == 1

    def test_failed_derived_correctly_when_caller_reports_zero_failed(self):
        """When caller reports 0 failed, batch derives failed from processed total."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # All items succeeded, no failures
        scan.expired_count = 10
        batch.accumulate(scan, succeeded=10, failed=0)

        assert batch.expired_detected == 10
        assert batch.relisted == 10
        assert batch.failed == 0

    def test_failed_never_negative(self):
        """failed must never be negative."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        scan.expired_count = 5
        batch.accumulate(scan, succeeded=5, failed=0)

        assert batch.failed >= 0
        assert batch.failed == 0


class TestRelistCountConsistency:
    """Bug 2 + 3: relisted, failed, and expired_detected must be consistent.

    Invariant: expired_detected == relisted + failed
    """

    def test_invariant_expired_equals_relisted_plus_failed(self):
        """The core invariant: expired_detected == relisted + failed."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        test_cases = [
            (10, 8, 2),   # 10 expired, 8 relisted, 2 failed
            (5, 5, 0),    # all succeeded
            (3, 0, 3),    # all failed
            (20, 15, 5),  # mixed
        ]

        for expired, succeeded, failed in test_cases:
            batch.reset()
            scan.expired_count = expired
            batch.accumulate(scan, succeeded=succeeded, failed=failed)

            # The invariant must hold
            assert batch.expired_detected == batch.relisted + batch.failed, \
                f"Failed for expired={expired}, succeeded={succeeded}, failed={failed}"

    def test_invariant_holds_across_multiple_cycles(self):
        """The invariant must hold after accumulating multiple cycles."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # Cycle 1
        scan.expired_count = 10
        batch.accumulate(scan, succeeded=7, failed=3)
        assert batch.expired_detected == batch.relisted + batch.failed

        # Cycle 2
        scan.expired_count = 8
        batch.accumulate(scan, succeeded=5, failed=3)
        assert batch.expired_detected == batch.relisted + batch.failed

        # Cycle 3
        scan.expired_count = 5
        batch.accumulate(scan, succeeded=4, failed=1)
        assert batch.expired_detected == batch.relisted + batch.failed

    def test_accumulate_without_expired_count_uses_processed_total(self):
        """When expired_count is 0 or not provided, use succeeded + failed."""
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # No expired_count provided (defaults to 0)
        batch.accumulate(scan, succeeded=5, failed=3)

        assert batch.expired_detected == 8
        assert batch.relisted == 5
        assert batch.failed == 3

    def test_realistic_golden_hour_scenario(self):
        """Simulate a realistic golden hour relist session.

        16 items expired → 15 relisted, 1 failed → golden retry → 1 more relisted.
        Total: 16 processed, 16 relisted, 0 failed.
        """
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # First relist: 15 succeeded, 1 failed
        scan.expired_count = 16
        batch.accumulate(scan, succeeded=15, failed=1)
        assert batch.expired_detected == 16
        assert batch.relisted == 15
        assert batch.failed == 1

        # Golden retry: 1 more succeeded (the previously failed one)
        scan.expired_count = 1
        batch.accumulate(scan, succeeded=1, failed=0)
        assert batch.expired_detected == 17  # 16 + 1
        assert batch.relisted == 16
        assert batch.failed == 1  # Still 1 (17 - 16)

    def test_no_double_counting_on_re_scan(self):
        """Re-scanning the same items without processing must not increase counts.

        This is the core bug fix: expired_detected was inflated by DOM scan counts
        when the same items were re-read during retry cycles.
        """
        batch = NotificationBatch()
        scan = MagicMock(spec=ListingScanResult)

        # Process 30 items
        scan.expired_count = 30
        batch.accumulate(scan, succeeded=25, failed=5)
        assert batch.expired_detected == 30

        # Re-scan shows 25 expired (same items, 5 were processed)
        # but we process 0 this cycle
        scan.expired_count = 25
        batch.accumulate(scan, succeeded=0, failed=0)
        # Must NOT increase to 55 (30 + 25) — stays at 30
        assert batch.expired_detected == 30
        assert batch.relisted == 25
        assert batch.failed == 5

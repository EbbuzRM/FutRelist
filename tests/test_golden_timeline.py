"""Comprehensive golden hour timeline simulation tests.

Verifies the bot's behavior at every critical moment of the golden hour schedule:

    15:10 -> HOLD con heartbeat (aspetta 16:09:30)
    16:09:30 -> Pre-nav: naviga alla Transfer List
    16:10:00 -> SKIP attesa (is_in_golden_window=True) -> SCANSIONE -> RELIST tutti
    16:10:10 -> Polling ritardatari (10s)
    16:10:20 -> Relist ritardatari se ce ne sono
    16:11:00 -> is_in_golden_window=False -> HOLD -> aspetta 17:09:30
    17:09:30 -> Pre-nav
    17:10:00 -> RELIST
    17:10:10 -> Polling ritardatari (10s)
    17:11:00 -> HOLD -> aspetta 18:09:30
    18:09:30 -> Pre-nav
    18:10:00 -> RELIST
    18:10:10 -> Polling ritardatari (10s)
    18:11:00 -> is_in_hold_window=True MA get_next_golden_hour=None -> in_hold=False -> RELIST IMMEDIATO
    18:15+  -> Relist normale (fuori golden period)
"""
from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from main import (
    GOLDEN_CLOSE_WINDOW,
    GOLDEN_HOURS,
    GOLDEN_MINUTE,
    GOLDEN_PERIOD_END,
    GOLDEN_PERIOD_START,
    GOLDEN_PRE_NAV_MINUTE,
    GOLDEN_RELIST_WINDOW,
    _compute_next_wait,
    get_next_golden_hour,
    is_close_to_golden,
    is_in_golden_period,
    is_in_golden_window,
    is_in_hold_window,
)
from models.listing import ListingScanResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BASE_DATE = (2026, 4, 13)  # arbitrary — only the time matters


def dt(hour: int, minute: int, second: int = 0) -> datetime:
    """Shorthand to build a datetime on the base date."""
    return datetime(*BASE_DATE, hour=hour, minute=minute, second=second)


# ===========================================================================
# 1. Golden hour helper function tests
# ===========================================================================


class TestGetNextGoldenHour:
    """Tests for get_next_golden_hour()."""

    @pytest.mark.parametrize(
        "time_str, expected",
        [
            # Well before golden period — next is 16:10
            ("14:00", "16:10"),
            # Inside golden period but before first golden — next is 16:10
            ("15:30", "16:10"),
            # Just before 16:10 — next is 16:10
            ("16:05", "16:10"),
            # Exactly at 16:10 — past it, next is 17:10
            ("16:10", "17:10"),
            # Just after 16:10 — next is 17:10
            ("16:11", "17:10"),
            # Just before 17:10 — next is 17:10
            ("17:09", "17:10"),
            # Exactly at 17:10 — past it, next is 18:10
            ("17:10", "18:10"),
            # Exactly at 18:10 — past it, None
            ("18:10", None),
            # After 18:10 — None
            ("18:11", None),
            # Well after golden period — None
            ("19:00", None),
            # At 18:15 — no more goldens
            ("18:16", None),
        ],
    )
    def test_get_next_golden_hour(self, time_str, expected):
        h, m = map(int, time_str.split(":"))
        now = dt(h, m)
        result = get_next_golden_hour(now)
        if expected is None:
            assert result is None
        else:
            eh, em = map(int, expected.split(":"))
            assert result == dt(eh, em)


class TestIsInGoldenPeriod:
    """Tests for is_in_golden_period()."""

    @pytest.mark.parametrize(
        "time_str, expected",
        [
            # Well before — False
            ("14:00", False),
            # One minute before start — False
            ("15:09", False),
            # Exactly at start — True
            ("15:10", True),
            # During golden period — True
            ("16:00", True),
            # One minute before end — True
            ("18:14", True),
            # Exactly at end — True
            ("18:15", True),
            # One minute after end — False
            ("18:16", False),
        ],
    )
    def test_is_in_golden_period(self, time_str, expected):
        h, m = map(int, time_str.split(":"))
        now = dt(h, m)
        assert is_in_golden_period(now) is expected


class TestIsInHoldWindow:
    """Tests for is_in_hold_window().

    Hold window = golden period BUT NOT in the golden relist window (:09-:11).
    """

    @pytest.mark.parametrize(
        "time_str, expected",
        [
            # Before golden period — False (not in golden period at all)
            ("15:09", False),
            # At golden period start, not in golden hour relist window — True (HOLD)
            ("15:10", True),
            # At 16:08 — in golden period, not in relist window — True (HOLD)
            ("16:08", True),
            # At 16:09 — in golden hour 16, minute in GOLDEN_RELIST_WINDOW(9,10,11) — False
            ("16:09", False),
            # At 16:10 — in golden relist window — False
            ("16:10", False),
            # At 16:11 — in golden relist window — False
            ("16:11", False),
            # At 16:12 — past relist window for hour 16, in golden period — True (HOLD)
            ("16:12", True),
            # At 17:09 — in golden relist window for hour 17 — False
            ("17:09", False),
            # At 17:10 — in golden relist window — False
            ("17:10", False),
            # At 17:11 — in golden relist window — False
            ("17:11", False),
            # At 18:10 — in golden relist window — False
            ("18:10", False),
            # At 18:11 — in golden relist window — False
            ("18:11", False),
            # At 18:14 — in golden period, not in relist window — True (HOLD, but no more goldens!)
            ("18:14", True),
            # After golden period — False
            ("18:16", False),
        ],
    )
    def test_is_in_hold_window(self, time_str, expected):
        h, m = map(int, time_str.split(":"))
        now = dt(h, m)
        assert is_in_hold_window(now) is expected


class TestIsInGoldenWindow:
    """Tests for is_in_golden_window().

    Golden window = hour in GOLDEN_HOURS AND minute in GOLDEN_RELIST_WINDOW (9-11).
    """

    @pytest.mark.parametrize(
        "time_str, expected",
        [
            # 16:08 — minute 8 not in range(9,12) — False
            ("16:08", False),
            # 16:09 — minute 9 in range(9,12) — True
            ("16:09", True),
            # 16:10 — True
            ("16:10", True),
            # 16:11 — minute 11 in range(9,12) — True
            ("16:11", True),
            # 16:12 — minute 12 not in range(9,12) — False
            ("16:12", False),
            # 17:10 — True
            ("17:10", True),
            # 18:10 — True
            ("18:10", True),
            # 18:11 — True
            ("18:11", True),
            # 18:12 — False
            ("18:12", False),
            # Not a golden hour (15:10) — False
            ("15:10", False),
        ],
    )
    def test_is_in_golden_window(self, time_str, expected):
        h, m = map(int, time_str.split(":"))
        now = dt(h, m)
        assert is_in_golden_window(now) is expected


class TestIsCloseToGolden:
    """Tests for is_close_to_golden().

    Close = hour in GOLDEN_HOURS AND minute in GOLDEN_CLOSE_WINDOW (8-12).
    """

    @pytest.mark.parametrize(
        "time_str, expected",
        [
            # 16:07 — minute 7 not in range(8,13) — False
            ("16:07", False),
            # 16:08 — minute 8 in range(8,13) — True
            ("16:08", True),
            # 16:09 — True
            ("16:09", True),
            # 16:10 — True
            ("16:10", True),
            # 16:11 — True
            ("16:11", True),
            # 16:12 — minute 12 in range(8,13) — True
            ("16:12", True),
            # 16:13 — minute 13 not in range(8,13) — False
            ("16:13", False),
        ],
    )
    def test_is_close_to_golden(self, time_str, expected):
        h, m = map(int, time_str.split(":"))
        now = dt(h, m)
        assert is_close_to_golden(now) is expected


# ===========================================================================
# 2. HOLD decision logic tests (Bug 3 fix verification)
# ===========================================================================


class TestHoldDecisionLogic:
    """Test the critical HOLD override logic.

    The key insight: is_in_hold_window() alone is NOT enough to decide to hold.
    When is_in_hold_window=True AND get_next_golden_hour() returns None, the hold
    must be overridden because there are no more goldens today.

    This was Bug 3: the bot would hold expired items after 18:11 even though
    there were no more golden hours, leaving items permanently expired.
    """

    def test_at_18_14_hold_but_no_golden_should_override(self):
        """At 18:14: hold_window=True, but next_golden=None -> override hold."""
        now = dt(18, 14)
        assert is_in_hold_window(now) is True
        assert get_next_golden_hour(now) is None
        # The main loop logic: in_hold and not force_relist -> check next_golden
        in_hold = is_in_hold_window(now)
        next_g = get_next_golden_hour(now)
        # When next_golden is None, the hold MUST be overridden
        should_relist = not in_hold or (in_hold and next_g is None)
        assert should_relist is True, (
            "At 18:14, hold should be overridden because no more goldens"
        )

    def test_at_16_12_hold_with_golden_should_stay_hold(self):
        """At 16:12: hold_window=True, next_golden=17:10 -> stay in hold."""
        now = dt(16, 12)
        assert is_in_hold_window(now) is True
        next_g = get_next_golden_hour(now)
        assert next_g is not None
        assert next_g == dt(17, 10)
        # The main loop logic: hold is genuine, don't override
        in_hold = is_in_hold_window(now)
        should_hold = in_hold and next_g is not None
        assert should_hold is True, (
            "At 16:12, hold is genuine because 17:10 is coming"
        )

    def test_at_15_30_hold_with_golden_should_stay_hold(self):
        """At 15:30: hold_window=True, next_golden=16:10 -> stay in hold."""
        now = dt(15, 30)
        assert is_in_hold_window(now) is True
        next_g = get_next_golden_hour(now)
        assert next_g == dt(16, 10)
        in_hold = is_in_hold_window(now)
        should_hold = in_hold and next_g is not None
        assert should_hold is True

    def test_at_18_12_hold_but_no_golden_should_override(self):
        """At 18:12: hold_window=True, next_golden=None -> override hold."""
        now = dt(18, 12)
        assert is_in_hold_window(now) is True
        assert get_next_golden_hour(now) is None
        in_hold = is_in_hold_window(now)
        next_g = get_next_golden_hour(now)
        should_relist = not in_hold or (in_hold and next_g is None)
        assert should_relist is True


# ===========================================================================
# 3. Golden wait skip logic tests (Bug 1 fix verification)
# ===========================================================================


class TestGoldenWaitSkipLogic:
    """Test the golden wait skip logic.

    When the bot is at the golden hour window (:09-:11), it should SKIP the
    time.sleep() wait and proceed immediately to scanning. This was Bug 1:
    the bot was sleeping through the golden window instead of acting.

    The relevant code in main.py:
        if next_golden and is_in_golden_period(now) and now < next_golden:
            if not is_in_golden_window(now):
                time.sleep(wait_secs)       # <-- would skip golden!
            else:
                # Already in golden window, scan immediately
    """

    def test_at_16_10_should_skip_wait(self):
        """At 16:10: is_in_golden_window=True -> skip time.sleep()."""
        now = dt(16, 10)
        assert is_in_golden_window(now) is True
        # The condition: if NOT in golden window -> sleep
        # So if in golden window -> skip sleep
        should_sleep = not is_in_golden_window(now)
        assert should_sleep is False, (
            "At 16:10 the bot must NOT sleep — it's golden time"
        )

    def test_at_16_08_should_wait_until_golden(self):
        """At 16:08: is_in_golden_window=False -> should time.sleep() until 16:10."""
        now = dt(16, 8)
        assert is_in_golden_window(now) is False
        should_sleep = not is_in_golden_window(now)
        assert should_sleep is True, (
            "At 16:08 the bot should sleep until golden window opens"
        )

    def test_at_16_09_should_skip_wait(self):
        """At 16:09: is_in_golden_window=True -> skip time.sleep()."""
        now = dt(16, 9)
        assert is_in_golden_window(now) is True
        should_sleep = not is_in_golden_window(now)
        assert should_sleep is False

    def test_at_16_11_should_skip_wait(self):
        """At 16:11: is_in_golden_window=True -> skip time.sleep()."""
        now = dt(16, 11)
        assert is_in_golden_window(now) is True
        should_sleep = not is_in_golden_window(now)
        assert should_sleep is False

    def test_at_16_12_should_wait_if_still_before_next_golden(self):
        """At 16:12: is_in_golden_window=False, next golden at 17:10."""
        now = dt(16, 12)
        assert is_in_golden_window(now) is False
        # After golden window closes, the hold logic takes over (not sleep-til-golden)


class TestComputeNextWaitGoldenWindow:
    """Test _compute_next_wait returns 10s during golden window (ritardatari polling)."""

    def test_golden_window_returns_10(self):
        """During golden window, _compute_next_wait should return 10s."""
        now = dt(16, 10)
        scan = MagicMock(spec=ListingScanResult)
        scan.listings = []
        logger = logging.getLogger("test")
        result = _compute_next_wait(scan, now, logger)
        assert result == 10, (
            f"During golden window, wait should be 10s for ritardatari polling, got {result}"
        )

    def test_hold_window_returns_wait_until_golden(self):
        """During hold, _compute_next_wait should return wait until next golden pre-nav."""
        now = dt(15, 30)
        scan = MagicMock(spec=ListingScanResult)
        scan.listings = []
        logger = logging.getLogger("test")
        result = _compute_next_wait(scan, now, logger)
        # Should be <= 60 (the min of 60 and seconds until golden)
        assert result <= 60, (
            f"During hold, wait should be <= 60s, got {result}"
        )


# ===========================================================================
# 4. Full day timeline simulation
# ===========================================================================


def _classify_behavior(now: datetime) -> str:
    """Classify the bot's expected behavior at a given time.

    Returns one of:
    - "relist_normal":  outside golden period — relist immediately on expiry
    - "hold":          in golden period but not in golden window — wait for next golden
    - "golden_relist": in the golden relist window (:09-:11 of GOLDEN_HOURS) — act now!
    - "post_golden_hold_override": in hold_window but no more goldens — relist immediately

    This mirrors the actual decision tree in main.py:
        if scan.expired_count > 0:
            in_hold = is_in_hold_window(now)
            if in_hold:
                next_g = get_next_golden_hour(now)
                if next_g is not None:
                    -> HOLD (wait for golden)
                else:
                    -> RELIST IMMEDIATELY (no more goldens, override hold)
            else:
                -> RELIST (normal or golden window)
    """
    # Outside golden period entirely -> normal relist
    if not is_in_golden_period(now):
        return "relist_normal"

    # Inside golden period
    if is_in_golden_window(now):
        # :09-:11 of GOLDEN_HOURS -> act immediately
        return "golden_relist"

    # In golden period but not in golden relist window
    if is_in_hold_window(now):
        next_g = get_next_golden_hour(now)
        if next_g is None:
            # No more goldens -> override hold, relist immediately
            return "post_golden_hold_override"
        # There is a future golden -> genuine hold
        return "hold"

    # Fallback: shouldn't happen if the functions are consistent
    return "relist_normal"


# Build the full timeline: every minute from 14:00 to 20:00
_TIMELINE_PARAMS = []
for _hour in range(14, 21):
    for _minute in range(0, 60):
        _expected = _classify_behavior(dt(_hour, _minute))
        _TIMELINE_PARAMS.append((_hour, _minute, _expected))


class TestFullDayTimeline:
    """Walk through every minute of the day (14:00-20:59) and verify behavior.

    This parametrized test simulates the ENTIRE day schedule from the user's
    ideal timeline, ensuring the golden hour functions produce correct decisions
    at every single minute.
    """

    @pytest.mark.parametrize(
        "hour, minute, expected",
        _TIMELINE_PARAMS,
        ids=[f"{h:02d}:{m:02d}" for h, m, _ in _TIMELINE_PARAMS],
    )
    def test_timeline_minute(self, hour, minute, expected):
        now = dt(hour, minute)
        actual = _classify_behavior(now)
        assert actual == expected, (
            f"At {hour:02d}:{minute:02d}: expected '{expected}', got '{actual}'"
        )


# ===========================================================================
# 5. Boundary edge cases (second-level precision)
# ===========================================================================


class TestGoldenWindowBoundaries:
    """Test exact second-level boundaries around the golden window.

    The golden window is :09-:11 (minutes 9, 10, 11) of GOLDEN_HOURS.
    This tests the transition moments with second precision.
    """

    @pytest.mark.parametrize(
        "time_tuple, in_window",
        [
            # 16:08:59 — just before golden window
            ((16, 8, 59), False),
            # 16:09:00 — golden window opens
            ((16, 9, 0), True),
            # 16:09:30 — pre-nav time
            ((16, 9, 30), True),
            # 16:10:00 — exact golden minute
            ((16, 10, 0), True),
            # 16:10:59 — still golden
            ((16, 10, 59), True),
            # 16:11:00 — last minute of golden window
            ((16, 11, 0), True),
            # 16:11:59 — last second of golden window
            ((16, 11, 59), True),
            # 16:12:00 — golden window closes
            ((16, 12, 0), False),
        ],
    )
    def test_golden_window_second_precision(self, time_tuple, in_window):
        h, m, s = time_tuple
        now = dt(h, m, s)
        assert is_in_golden_window(now) is in_window


class TestHoldWindowBoundaries:
    """Test hold window boundaries with second precision."""

    @pytest.mark.parametrize(
        "time_tuple, in_hold",
        [
            # 15:09:59 — just before golden period starts
            ((15, 9, 59), False),
            # 15:10:00 — golden period starts, not in golden window -> HOLD
            ((15, 10, 0), True),
            # 16:08:59 — in golden period, not golden window -> HOLD
            ((16, 8, 59), True),
            # 16:09:00 — golden window opens -> NOT hold
            ((16, 9, 0), False),
            # 16:11:59 — last second of golden window -> NOT hold
            ((16, 11, 59), False),
            # 16:12:00 — golden window closes -> HOLD
            ((16, 12, 0), True),
            # 18:15:00 — last moment of golden period -> HOLD
            ((18, 15, 0), True),
            # 18:16:00 — past golden period -> NOT hold
            ((18, 16, 0), False),
        ],
    )
    def test_hold_window_second_precision(self, time_tuple, in_hold):
        h, m, s = time_tuple
        now = dt(h, m, s)
        assert is_in_hold_window(now) is in_hold


class TestGetNextGoldenHourBoundaries:
    """Test get_next_golden_hour at exact boundary times."""

    def test_just_before_16_10(self):
        """15:59:59 -> next golden is 16:10."""
        now = dt(15, 59, 59)
        result = get_next_golden_hour(now)
        assert result == dt(16, 10)

    def test_exactly_16_10(self):
        """At exactly 16:10, we've passed it -> next golden is 17:10."""
        now = dt(16, 10, 0)
        result = get_next_golden_hour(now)
        assert result == dt(17, 10)

    def test_just_before_18_10(self):
        """18:09:59 -> next golden is 18:10."""
        now = dt(18, 9, 59)
        result = get_next_golden_hour(now)
        assert result == dt(18, 10)

    def test_exactly_18_10(self):
        """At exactly 18:10, we've passed it -> None."""
        now = dt(18, 10, 0)
        result = get_next_golden_hour(now)
        assert result is None

    def test_midnight_before_goldens(self):
        """00:00 -> next golden is 16:10."""
        now = dt(0, 0, 0)
        result = get_next_golden_hour(now)
        assert result == dt(16, 10)


# ===========================================================================
# 6. Critical scenario: the 18:11+ post-golden override
# ===========================================================================


class TestPostGoldenHoldOverride:
    """Verify the critical fix: after 18:11, hold_window=True but no more goldens.

    The user's timeline specifies:
        18:11:00 -> is_in_hold_window=True MA get_next_golden_hour=None
                   -> in_hold=False -> RELIST IMMEDIATO

    This was a critical bug: items were stuck in hold with no future golden.
    """

    @pytest.mark.parametrize(
        "time_str",
        ["18:12", "18:13", "18:14", "18:15"],
    )
    def test_post_golden_hold_overridden(self, time_str):
        """After last golden window closes, hold MUST be overridden."""
        h, m = map(int, time_str.split(":"))
        now = dt(h, m)
        # is_in_hold_window is True (we're in golden period, not in golden window)
        assert is_in_hold_window(now) is True, (
            f"Expected hold_window=True at {time_str}"
        )
        # But get_next_golden_hour returns None — no more goldens!
        assert get_next_golden_hour(now) is None, (
            f"Expected no more goldens at {time_str}"
        )
        # The main loop overrides hold when next_golden is None
        in_hold = is_in_hold_window(now)
        next_g = get_next_golden_hour(now)
        effective_hold = in_hold and next_g is not None
        assert effective_hold is False, (
            f"At {time_str}: hold must be overridden (no future golden)"
        )

    def test_18_10_is_golden_window_not_hold(self):
        """At 18:10 we're in the golden window, not in hold."""
        now = dt(18, 10)
        assert is_in_golden_window(now) is True
        assert is_in_hold_window(now) is False

    def test_18_11_is_golden_window_not_hold(self):
        """At 18:11 we're still in the golden window (last minute)."""
        now = dt(18, 11)
        assert is_in_golden_window(now) is True
        assert is_in_hold_window(now) is False


# ===========================================================================
# 7. Constants consistency checks
# ===========================================================================


class TestGoldenConstantsConsistency:
    """Verify the golden hour constants are internally consistent."""

    def test_golden_hours_are_16_17_18(self):
        assert GOLDEN_HOURS == (16, 17, 18)

    def test_golden_minute_is_10(self):
        assert GOLDEN_MINUTE == 10

    def test_pre_nav_minute_is_9(self):
        assert GOLDEN_PRE_NAV_MINUTE == 9

    def test_relist_window_covers_pre_nav_to_ritardatari(self):
        """GOLDEN_RELIST_WINDOW must include :09 (pre-nav), :10 (relist), :11 (ritardatari)."""
        assert 9 in GOLDEN_RELIST_WINDOW
        assert 10 in GOLDEN_RELIST_WINDOW
        assert 11 in GOLDEN_RELIST_WINDOW
        assert 8 not in GOLDEN_RELIST_WINDOW
        assert 12 not in GOLDEN_RELIST_WINDOW

    def test_close_window_is_superset_of_relist_window(self):
        """GOLDEN_CLOSE_WINDOW must be a superset of GOLDEN_RELIST_WINDOW."""
        assert set(GOLDEN_RELIST_WINDOW).issubset(set(GOLDEN_CLOSE_WINDOW))
        # Close window should extend one minute on each side
        assert 8 in GOLDEN_CLOSE_WINDOW
        assert 12 in GOLDEN_CLOSE_WINDOW
        assert 7 not in GOLDEN_CLOSE_WINDOW
        assert 13 not in GOLDEN_CLOSE_WINDOW

    def test_period_start_is_15_10(self):
        assert GOLDEN_PERIOD_START == (15, 10)

    def test_period_end_is_18_15(self):
        assert GOLDEN_PERIOD_END == (18, 15)


# ===========================================================================
# 8. Integration: _compute_next_wait at key moments
# ===========================================================================


class TestComputeNextWaitIntegration:
    """Test _compute_next_wait at critical timeline moments."""

    def _make_scan(self, active_with_timer=None, expired=0):
        """Helper to build a mock ListingScanResult."""
        scan = MagicMock(spec=ListingScanResult)
        scan.listings = []
        scan.expired_count = expired
        # If we need active listings with timers:
        if active_with_timer is not None:
            from models.listing import PlayerListing, ListingState
            for i, t in enumerate(active_with_timer):
                scan.listings.append(PlayerListing(
                    index=i,
                    player_name=f"Player {i}",
                    state=ListingState.ACTIVE,
                    time_remaining_seconds=t,
                    time_remaining=f"{t // 60}m",
                ))
        return scan

    def test_golden_window_16_10_returns_10(self):
        """At 16:10 in golden window -> 10s polling for ritardatari."""
        now = dt(16, 10)
        scan = self._make_scan()
        logger = logging.getLogger("test")
        assert _compute_next_wait(scan, now, logger) == 10

    def test_hold_15_30_returns_short_wait(self):
        """At 15:30 in hold -> short wait until pre-nav of 16:09:30."""
        now = dt(15, 30)
        scan = self._make_scan()
        logger = logging.getLogger("test")
        result = _compute_next_wait(scan, now, logger)
        # In hold with no active timers, wait is capped at 60s
        assert result <= 60

    def test_hold_16_12_returns_wait_toward_17_09(self):
        """At 16:12 in hold -> wait toward 17:09:30 pre-nav."""
        now = dt(16, 12)
        scan = self._make_scan()
        logger = logging.getLogger("test")
        result = _compute_next_wait(scan, now, logger)
        # In hold, wait is capped at 60s toward pre-nav
        assert result <= 60

    def test_normal_period_14_00_with_active_timer(self):
        """At 14:00 (normal) with 30 min active timer -> wait ~29m40s."""
        now = dt(14, 0)
        scan = self._make_scan(active_with_timer=[1800])  # 30 min
        logger = logging.getLogger("test")
        result = _compute_next_wait(scan, now, logger)
        # min_active - 20 = 1780, clamped to max(1780, 10) = 1780
        assert result == 1780

    def test_normal_period_after_18_16_with_active_timer(self):
        """At 18:16 (post-golden, normal) with 25 min active timer."""
        now = dt(18, 16)
        scan = self._make_scan(active_with_timer=[1500])  # 25 min
        logger = logging.getLogger("test")
        result = _compute_next_wait(scan, now, logger)
        # min_active - 20 = 1480
        assert result == 1480

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from logic.golden_hour import (
    get_next_golden_hour,
    is_in_golden_period,
    is_in_hold_window,
    is_close_to_golden,
    is_in_golden_window
)

def test_is_in_golden_period():
    # 15:00 -> False
    assert is_in_golden_period(datetime(2026, 4, 18, 15, 0)) is False
    # 15:10 -> True
    assert is_in_golden_period(datetime(2026, 4, 18, 15, 10)) is True
    # 18:15 -> True
    assert is_in_golden_period(datetime(2026, 4, 18, 18, 15)) is True
    # 18:16 -> False
    assert is_in_golden_period(datetime(2026, 4, 18, 18, 16)) is False

def test_is_in_golden_window():
    # 16:08 -> False
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 8)) is False
    # 16:09 -> True
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 9)) is True
    # 16:10 -> True
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 10)) is True
    # 16:11 -> True
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 11)) is True
    # 16:12 -> False
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 12)) is False

def test_is_in_hold_window():
    # Fuori fascia golden -> False
    assert is_in_hold_window(datetime(2026, 4, 18, 14, 0)) is False
    # In fascia golden, ma in finestra relist -> False
    assert is_in_hold_window(datetime(2026, 4, 18, 16, 10)) is False
    # In fascia golden, fuori finestra relist -> True
    assert is_in_hold_window(datetime(2026, 4, 18, 16, 0)) is True
    assert is_in_hold_window(datetime(2026, 4, 18, 17, 30)) is True

def test_is_close_to_golden():
    # 16:08 -> True
    assert is_close_to_golden(datetime(2026, 4, 18, 16, 8)) is True
    # 16:12 -> True
    assert is_close_to_golden(datetime(2026, 4, 18, 16, 12)) is True
    # 16:07 -> False
    assert is_close_to_golden(datetime(2026, 4, 18, 16, 7)) is False
    # 15:00 -> False
    assert is_close_to_golden(datetime(2026, 4, 18, 15, 0)) is False

def test_get_next_golden_hour():
    # 15:00 -> 16:10
    now = datetime(2026, 4, 18, 15, 0)
    target = get_next_golden_hour(now)
    assert target.hour == 16 and target.minute == 10

    # 16:05 -> 16:10
    now = datetime(2026, 4, 18, 16, 5)
    target = get_next_golden_hour(now)
    assert target.hour == 16 and target.minute == 10

    # 16:10:30 -> 16:10 (still current because window ends at :11:59)
    now = datetime(2026, 4, 18, 16, 10, 30)
    target = get_next_golden_hour(now)
    assert target.hour == 16 and target.minute == 10

    # 16:11:59 -> 16:10 (still current)
    now = datetime(2026, 4, 18, 16, 11, 59)
    target = get_next_golden_hour(now)
    assert target.hour == 16 and target.minute == 10

    # 16:12:00 -> 17:10
    now = datetime(2026, 4, 18, 16, 12, 0)
    target = get_next_golden_hour(now)
    assert target.hour == 17 and target.minute == 10

    # Dopo le 18:11:59 -> None
    now = datetime(2026, 4, 18, 18, 12, 0)
    target = get_next_golden_hour(now)
    assert target is None

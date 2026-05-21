from datetime import datetime

from logic.golden_hour import (
    get_next_golden_hour,
    is_close_to_golden,
    is_in_golden_period,
    is_in_golden_window,
    is_in_hold_window,
)


def test_is_in_golden_period():
    # 16:09 -> False (periodo inizia alle 16:10)
    assert is_in_golden_period(datetime(2026, 4, 18, 16, 9)) is False
    # 16:10 -> True
    assert is_in_golden_period(datetime(2026, 4, 18, 16, 10)) is True
    # 18:15 -> True
    assert is_in_golden_period(datetime(2026, 4, 18, 18, 15)) is True
    # 18:16 -> False
    assert is_in_golden_period(datetime(2026, 4, 18, 18, 16)) is False


def test_is_in_golden_window():
    # 16:09 — ora 16 non è golden hour -> False
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 9)) is False
    # 16:10 — non golden hour -> False
    assert is_in_golden_window(datetime(2026, 4, 18, 16, 10)) is False
    # 17:08 -> False
    assert is_in_golden_window(datetime(2026, 4, 18, 17, 8)) is False
    # 17:09 -> True
    assert is_in_golden_window(datetime(2026, 4, 18, 17, 9)) is True
    # 17:10 -> True
    assert is_in_golden_window(datetime(2026, 4, 18, 17, 10)) is True
    # 17:11 -> True
    assert is_in_golden_window(datetime(2026, 4, 18, 17, 11)) is True
    # 17:12 -> False
    assert is_in_golden_window(datetime(2026, 4, 18, 17, 12)) is False


def test_is_in_hold_window():
    # Fuori fascia golden -> False
    assert is_in_hold_window(datetime(2026, 4, 18, 14, 0)) is False
    # 16:10 — in fascia golden, non in finestra relist -> True (HOLD verso 17:10)
    assert is_in_hold_window(datetime(2026, 4, 18, 16, 10)) is True
    # 17:10 — in finestra relist -> False
    assert is_in_hold_window(datetime(2026, 4, 18, 17, 10)) is False
    assert is_in_hold_window(datetime(2026, 4, 18, 17, 30)) is True


def test_is_close_to_golden():
    # 16:08 — ora 16 non è golden hour -> False
    assert is_close_to_golden(datetime(2026, 4, 18, 16, 8)) is False
    # 17:08 -> True
    assert is_close_to_golden(datetime(2026, 4, 18, 17, 8)) is True
    # 17:12 -> True
    assert is_close_to_golden(datetime(2026, 4, 18, 17, 12)) is True
    # 17:07 -> False
    assert is_close_to_golden(datetime(2026, 4, 18, 17, 7)) is False
    # 16:00 -> False
    assert is_close_to_golden(datetime(2026, 4, 18, 16, 0)) is False


def test_get_next_golden_hour():
    # 15:00 -> 17:10
    now = datetime(2026, 4, 18, 15, 0)
    target = get_next_golden_hour(now)
    assert target.hour == 17 and target.minute == 10

    # 16:05 -> 17:10
    now = datetime(2026, 4, 18, 16, 5)
    target = get_next_golden_hour(now)
    assert target.hour == 17 and target.minute == 10

    # 17:10:30 -> 18:10 (next future, not current)
    now = datetime(2026, 4, 18, 17, 10, 30)
    target = get_next_golden_hour(now)
    assert target.hour == 18 and target.minute == 10

    # 17:11:59 -> 18:10 (next future)
    now = datetime(2026, 4, 18, 17, 11, 59)
    target = get_next_golden_hour(now)
    assert target.hour == 18 and target.minute == 10

    # 18:12:00 -> None
    now = datetime(2026, 4, 18, 18, 12, 0)
    target = get_next_golden_hour(now)
    assert target is None

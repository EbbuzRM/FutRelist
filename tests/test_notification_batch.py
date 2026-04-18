import pytest
from datetime import datetime
from unittest.mock import MagicMock
from core.notification_batch import NotificationBatch
from models.listing import ListingScanResult

def test_notification_batch_accumulation():
    batch = NotificationBatch()
    scan = MagicMock(spec=ListingScanResult)
    scan.expired_count = 5
    
    batch.accumulate(scan, succeeded=3, failed=2)
    assert batch.relisted == 3
    assert batch.failed == 2
    assert batch.cycles == 1
    assert batch.expired_detected == 5

    batch.accumulate(scan, succeeded=2, failed=0)
    assert batch.relisted == 5
    assert batch.failed == 2
    assert batch.cycles == 2
    assert batch.expired_detected == 10

def test_notification_batch_flush_logic():
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    
    # Case 1: wait is short, cycles low -> False
    assert batch.is_ready_to_flush(current_wait=30) is False
    
    # Case 2: wait is long (> 120) -> True
    # Simulate some activity first
    batch.cycles = 1
    batch.relisted = 1
    assert batch.is_ready_to_flush(current_wait=150) is True

def test_notification_batch_no_activity_no_flush():
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    
    # Simulate cycles but NO activity (no relists, no failures)
    batch.cycles = 1
    batch.relisted = 0
    batch.failed = 0
    
    # Should NOT flush even if wait is long
    assert batch.is_ready_to_flush(current_wait=150) is False
    # Should NOT flush even if cycles are high
    batch.cycles = 6
    assert batch.is_ready_to_flush(current_wait=30) is False

def test_notification_batch_activity_flushes():
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    batch.cycles = 1
    
    # Case 1: At least one relist -> Should flush if wait is long
    batch.relisted = 1
    batch.failed = 0
    assert batch.is_ready_to_flush(current_wait=150) is True
    
    batch.reset()
    batch.cycles = 1
    
    # Case 2: At least one failure -> Should flush if wait is long
    batch.relisted = 0
    batch.failed = 1
    assert batch.is_ready_to_flush(current_wait=150) is True

def test_notification_batch_reset():
    batch = NotificationBatch()
    batch.relisted = 10
    batch.failed = 2
    batch.cycles = 3
    
    batch.reset()
    assert batch.relisted == 0
    assert batch.failed == 0
    assert batch.cycles == 0

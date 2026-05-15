from datetime import datetime
from unittest.mock import MagicMock

from core.notification_batch import NotificationBatch
from models.listing import ListingScanResult


def test_notification_batch_accumulation():
    """Test che expired_detected usa succeeded + failed come proxy."""
    batch = NotificationBatch()

    # Crea un mock con expired_count impostato
    scan = MagicMock(spec=ListingScanResult)
    scan.expired_count = 5

    # expired_detected = succeeded + failed (proxy)
    batch.accumulate(scan, succeeded=3, failed=2)
    assert batch.relisted == 3
    assert batch.failed == 2
    assert batch.cycles == 1
    assert batch.expired_detected == 5  # 3 + 2 = 5

    # Secondo ciclo
    scan.expired_count = 3
    batch.accumulate(scan, succeeded=2, failed=1)
    assert batch.relisted == 5
    assert batch.failed == 3
    assert batch.cycles == 2
    assert batch.expired_detected == 8  # 5 + 3 = 8


def test_notification_batch_is_ready_to_flush_no_activity():
    """Test che is_ready_to_flush ritorna False senza attivita'."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)

    # cycles == 0 → False
    assert batch.is_ready_to_flush(current_wait=30) is False
    assert batch.is_ready_to_flush(current_wait=150) is False

    # expired_detected > 0 ma relisted == 0 e failed == 0 → False
    batch.cycles = 1
    batch.expired_detected = 5
    assert batch.is_ready_to_flush(current_wait=150) is False


def test_notification_batch_is_ready_to_flush_long_wait():
    """Test che flusha quando il prossimo wait e' lungo."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    batch.cycles = 1
    batch.relisted = 3
    batch.failed = 1

    # Wait corto → non pronto
    assert batch.is_ready_to_flush(current_wait=30) is False

    # Wait lungo (> batch_window) → pronto
    assert batch.is_ready_to_flush(current_wait=150) is True


def test_notification_batch_is_ready_to_flush_max_cycles():
    """Test che flusha quando si raggiunge max_cycles."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    batch.cycles = 5
    batch.relisted = 3
    batch.failed = 1

    # Max cycles raggiunto → pronto anche con wait corto
    assert batch.is_ready_to_flush(current_wait=30) is True


def test_notification_batch_is_ready_to_flush_time_elapsed():
    """Test che flusha se e' passato batch_window_seconds dall'ultimo flush."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    batch.cycles = 1
    batch.relisted = 3
    batch.failed = 1
    # Simula un flush avvenuto 130 secondi fa
    from datetime import timedelta

    batch.last_flush_time = datetime.now() - timedelta(seconds=130)

    # Tempo trascorso > batch_window → pronto
    assert batch.is_ready_to_flush(current_wait=30) is True


def test_notification_batch_is_ready_to_flush_not_yet():
    """Test che NON flusha se nessuna condizione e' soddisfatta."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    batch.cycles = 2
    batch.relisted = 3
    batch.failed = 1
    batch.last_flush_time = datetime.now()  # appena flushato

    # Nessuna condizione soddisfatta → non pronto
    assert batch.is_ready_to_flush(current_wait=30) is False


def test_notification_batch_no_activity_no_flush():
    """Test che flush_if_any non invia se non c'e' stata attivita'."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)

    # cycles == 0, quindi flush_if_any non dovrebbe inviare
    batch.flush_if_any(
        app_config=MagicMock(notifications=MagicMock(telegram_token="test", telegram_chat_id="123")),
        page=None,
        logger=MagicMock(),
    )
    assert batch.cycles == 0


def test_notification_batch_reset():
    """Test che reset() azzera tutti i contatori."""
    batch = NotificationBatch()
    batch.relisted = 10
    batch.failed = 2
    batch.cycles = 3
    batch.expired_detected = 15

    batch.reset()
    assert batch.relisted == 0
    assert batch.failed == 0
    assert batch.cycles == 0
    assert batch.expired_detected == 0
    assert batch.last_flush_time is not None


def test_notification_batch_flush_with_activity_and_long_wait():
    """Test che flush_if_any invia quando c'e' attivita' e wait lungo."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    scan = MagicMock(spec=ListingScanResult)
    scan.expired_count = 2
    scan.total_count = 10

    batch.accumulate(scan, succeeded=3, failed=1)

    app_config = MagicMock(notifications=MagicMock(telegram_token="test", telegram_chat_id="123"))
    mock_logger = MagicMock()

    # Con wait lungo → deve flushare
    # Simuliamo: impostiamo last_flush_time nel passato per far passare il time check
    from datetime import timedelta

    batch.last_flush_time = datetime.now() - timedelta(seconds=130)

    batch.flush_if_any(app_config, page=None, logger=mock_logger, scan=scan)
    assert batch.cycles == 0  # Resettato dopo flush
    assert batch.relisted == 0
    mock_logger.info.assert_called()


def test_notification_batch_flush_no_activity_no_send():
    """Test che flush_if_any NON invia se non c'e' attivita' reale."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    scan = MagicMock(spec=ListingScanResult)
    scan.expired_count = 2
    scan.total_count = 10

    # Accumula ma con zero succeeded e zero failed
    batch.accumulate(scan, succeeded=0, failed=0)

    app_config = MagicMock(notifications=MagicMock(telegram_token="test", telegram_chat_id="123"))
    mock_logger = MagicMock()

    # Anche con wait lungo, se relisted==0 e failed==0 → non flusha
    batch.flush_if_any(app_config, page=None, logger=mock_logger, scan=scan)
    assert batch.cycles == 1  # Non resettato
    assert batch.relisted == 0


def test_notification_batch_flush_force_sends():
    """Test che flush_if_any con force=True invia indipendentemente dalle condizioni."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    scan = MagicMock(spec=ListingScanResult)
    scan.expired_count = 2
    scan.total_count = 10

    batch.accumulate(scan, succeeded=3, failed=1)

    app_config = MagicMock(notifications=MagicMock(telegram_token="test", telegram_chat_id="123"))
    mock_logger = MagicMock()

    # Force=True → deve flushare anche se nessuna condizione e' soddisfatta
    batch.flush_if_any(app_config, page=None, logger=mock_logger, scan=scan, force=True)
    assert batch.cycles == 0  # Resettato dopo flush
    assert batch.relisted == 0
    mock_logger.info.assert_called()


def test_notification_batch_flush_alias():
    """Test che flush() e' un alias di flush_if_any()."""
    batch = NotificationBatch(batch_window_seconds=120, max_cycles=5)
    scan = MagicMock(spec=ListingScanResult)
    scan.expired_count = 2
    scan.total_count = 10

    batch.accumulate(scan, succeeded=3, failed=1)

    app_config = MagicMock(notifications=MagicMock(telegram_token="test", telegram_chat_id="123"))
    mock_logger = MagicMock()

    # flush() con force=True → deve flushare
    batch.flush(app_config, page=None, logger=mock_logger, scan=scan, force=True)
    assert batch.cycles == 0
    assert batch.relisted == 0

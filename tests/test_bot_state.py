"""Test per BotState — dataclass thread-safe per stato condiviso del bot."""
import threading
import time
from datetime import datetime
from bot_state import BotState


class TestBotStateInit:
    """Test di inizializzazione BotState."""

    def test_default_values(self):
        """BotState() inizializza con valori di default corretti."""
        state = BotState()
        assert state.is_paused() is False
        assert state.consume_force_relist() is False
        assert state.cycle_count == 0
        assert state.last_relisted == 0
        assert state.last_failed == 0
        assert state.last_scan_time is None

    def test_initial_status_dict(self):
        """get_status() restituisce dict con tutte le chiavi."""
        state = BotState()
        status = state.get_status()
        assert "paused" in status
        assert "force_relist" in status
        assert "cycle_count" in status
        assert "last_relisted" in status
        assert "last_failed" in status
        assert "last_scan_time" in status
        assert status["paused"] is False
        assert status["force_relist"] is False


class TestBotStatePaused:
    """Test per pause/resume."""

    def test_set_paused_true(self):
        """set_paused(True) → is_paused() returns True."""
        state = BotState()
        state.set_paused(True)
        assert state.is_paused() is True

    def test_set_paused_false(self):
        """set_paused(False) → is_paused() returns False."""
        state = BotState()
        state.set_paused(True)
        state.set_paused(False)
        assert state.is_paused() is False

    def test_pause_unpause_cycle(self):
        """Ciclo completo pause → resume → pause."""
        state = BotState()
        state.set_paused(True)
        assert state.is_paused() is True
        state.set_paused(False)
        assert state.is_paused() is False
        state.set_paused(True)
        assert state.is_paused() is True


class TestBotStateForceRelist:
    """Test per force relist flag (consume-on-read)."""

    def test_set_force_relist_true(self):
        """set_force_relist(True) → consume_force_relist() returns True."""
        state = BotState()
        state.set_force_relist(True)
        assert state.consume_force_relist() is True

    def test_consume_resets_flag(self):
        """consume_force_relist() resets flag to False after reading."""
        state = BotState()
        state.set_force_relist(True)
        state.consume_force_relist()
        assert state.consume_force_relist() is False

    def test_consume_when_false_returns_false(self):
        """consume_force_relist() when flag is False → returns False."""
        state = BotState()
        assert state.consume_force_relist() is False

    def test_set_force_relist_false(self):
        """set_force_relist(False) → consume returns False."""
        state = BotState()
        state.set_force_relist(False)
        assert state.consume_force_relist() is False


class TestBotStateUpdateStats:
    """Test per aggiornamento statistiche."""

    def test_update_cycle_count(self):
        """update_stats(cycle=1) incrementa cycle_count."""
        state = BotState()
        state.update_stats(cycle=1)
        assert state.cycle_count == 1

    def test_update_relisted_count(self):
        """update_stats(relisted=3) incrementa last_relisted."""
        state = BotState()
        state.update_stats(relisted=3)
        assert state.last_relisted == 3

    def test_update_failed_count(self):
        """update_stats(failed=1) incrementa last_failed."""
        state = BotState()
        state.update_stats(failed=1)
        assert state.last_failed == 1

    def test_update_all_stats(self):
        """update_stats(cycle=1, relisted=3, failed=1) aggiorna tutto."""
        state = BotState()
        state.update_stats(cycle=1, relisted=3, failed=1)
        assert state.cycle_count == 1
        assert state.last_relisted == 3
        assert state.last_failed == 1

    def test_update_sets_scan_time(self):
        """update_stats() imposta last_scan_time a datetime.now()."""
        state = BotState()
        assert state.last_scan_time is None
        state.update_stats(cycle=1)
        assert state.last_scan_time is not None
        assert isinstance(state.last_scan_time, datetime)

    def test_update_accumulates(self):
        """Chiamate multiple in un singolo ciclo accumulano. Nuovi cicli resettano last_* ma non total_*."""
        state = BotState()
        # Inizio ciclo 1 con relist e fail
        state.update_stats(cycle=1, relisted=2, failed=0)
        # Stesso ciclo, altri relist
        state.update_stats(relisted=3, failed=1)
        assert state.cycle_count == 1
        assert state.last_relisted == 5
        assert state.last_failed == 1
        assert state.total_relisted == 5
        
        # Nuovo ciclo 2
        state.update_stats(cycle=1, relisted=1, failed=1)
        assert state.cycle_count == 2
        assert state.last_relisted == 1  # Resettato
        assert state.total_relisted == 6 # Accumulato storicamente


class TestBotStateThreadSafety:
    """Test per thread safety con accesso concorrente."""

    def test_concurrent_set_paused(self):
        """100 thread concorrenti non corrompono lo stato."""
        state = BotState()
        errors = []

        def toggle(n: int):
            try:
                state.set_paused(n % 2 == 0)
                _ = state.is_paused()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=toggle, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Lo stato finale deve essere consistente (True o False)
        result = state.is_paused()
        assert result in (True, False)

    def test_concurrent_get_status(self):
        """100 thread leggono get_status senza errori."""
        state = BotState()
        results = []

        def read_status():
            try:
                s = state.get_status()
                results.append(s)
            except Exception as e:
                results.append(e)

        threads = [threading.Thread(target=read_status) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 100
        assert all(isinstance(r, dict) for r in results)

    def test_concurrent_mixed_operations(self):
        """Thread misti (write + read) non corrompono lo stato."""
        state = BotState()
        errors = []

        def writer():
            try:
                for i in range(50):
                    state.set_paused(i % 2 == 0)
                    state.set_force_relist(i % 3 == 0)
                    state.update_stats(cycle=1, relisted=1, failed=0)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    _ = state.is_paused()
                    _ = state.consume_force_relist()
                    _ = state.get_status()
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

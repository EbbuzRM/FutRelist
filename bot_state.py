"""BotState — stato condiviso thread-safe per il bot di relist.

Fornisce un'interfaccia sicura per leggere e modificare lo stato del bot
da thread diversi (es. thread principale del bot + thread Telegram polling).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable


class RebootRequestError(Exception):
    """Eccezione sollevata per forzare un riavvio pulito della logica da parte del loop principale."""
    pass


@dataclass
class BotState:
    """Stato condiviso del bot, thread-safe tramite threading.Lock.

    Attributi:
        paused: Se True, il bot sospende il relist automatico.
        force_relist: Se True, forza un relist al prossimo ciclo (consumato alla lettura).
        cycle_count: Numero totale di cicli di scansione eseguiti.
        last_relisted: Numero di listing relistati nell'ultimo ciclo.
        last_failed: Numero di listing falliti nell'ultimo ciclo.
        last_scan_time: Timestamp dell'ultima scansione completata.
    """

    _paused: bool = field(default=False, repr=False)
    _force_relist: bool = field(default=False, repr=False)
    _console_session_active: bool = field(default=False, repr=False)
    _reboot_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _command_event: threading.Event = field(default_factory=threading.Event, repr=False)
    cycle_count: int = field(default=0)
    last_relisted: int = field(default=0)
    last_failed: int = field(default=0)
    total_relisted: int = field(default=0)
    total_failed: int = field(default=0)
    last_scan_time: datetime | None = field(default=None)
    last_relisted_by_bot: datetime | None = field(default=None)  # Timestamp dell'ultimo relist eseguito dal bot
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Console mode: deep sleep, zero WebApp interaction
    _console_mode: bool = field(default=False, repr=False)
    _console_mode_until: datetime | None = field(default=None, repr=False)

    # Command queue for thread-safe operations
    _pending_commands: list[dict] = field(default_factory=list, repr=False)

    def set_console_session_active(self, active: bool) -> None:
        """Imposta il flag di sessione console attiva (rischio ban)."""
        with self._lock:
            self._console_session_active = active

    def is_console_session_active(self) -> bool:
        """Ritorna True se è attiva una sessione console."""
        with self._lock:
            return self._console_session_active

    # --- Pause / Resume ---

    def set_paused(self, value: bool) -> None:
        """Imposta lo stato di pausa del bot."""
        with self._lock:
            self._paused = value

    def is_paused(self) -> bool:
        """Restituisce True se il bot è in pausa o in console mode."""
        with self._lock:
            # Console mode auto-resume check
            if self._console_mode and self._console_mode_until:
                if datetime.now() >= self._console_mode_until:
                    self._console_mode = False
                    self._console_mode_until = None
            return self._paused or self._console_mode

    # --- Reboot ---

    def request_reboot(self) -> None:
        """Segnala al main loop che il bot deve riavviarsi.

        Usa threading.Event: sveglia istantaneamente qualsiasi
        wait_interruptible() in corso nel main thread.
        """
        self._reboot_event.set()

    def is_reboot_requested(self) -> bool:
        """Restituisce True se è stato richiesto un reboot."""
        return self._reboot_event.is_set()

    def clear_reboot_event(self) -> None:
        """Resetta l'evento di reboot."""
        self._reboot_event.clear()

    def wait_interruptible(self, seconds: float) -> bool:
        """Attende fino a `seconds` ma si interrompe subito se arriva un reboot o un comando.

        Sostituisce time.sleep() nel main loop.
        Ritorna True se il reboot è stato richiesto (sleep interrotto).
        """
        # Aspettiamo fino a seconds, svegliati da reboot o comando
        # Nota: usiamo un piccolo trucco, aspettiamo reboot_event, ma se non arriva
        # controlliamo se c'è un comando o un reboot effettivo.
        start = datetime.now()
        while (datetime.now() - start).total_seconds() < seconds:
            remaining = seconds - (datetime.now() - start).total_seconds()
            if remaining <= 0: break
            
            # Aspetta reboot (il timeout è l'unica cosa che ci serve qui)
            # ma controlliamo anche i comandi ogni 2 secondi
            if self._reboot_event.wait(timeout=min(remaining, 2.0)):
                return True # Reboot!
            
            if self.has_commands():
                return False # Comando in coda, svegliati (ma non è reboot)
                
        return self._reboot_event.is_set()

    # --- Force Relist (flag consumato alla lettura) ---

    def set_force_relist(self, value: bool) -> None:
        """Imposta il flag di force relist."""
        with self._lock:
            self._force_relist = value

    def consume_force_relist(self) -> bool:
        """Restituisce il valore del flag e lo resetta a False.

        Pattern consume-on-read: il flag può essere letto una sola volta.
        """
        with self._lock:
            value = self._force_relist
            self._force_relist = False
            return value

    # --- Command Queue (for thread-safe Playwright operations) ---

    def queue_command(self, command_type: str, callback: Callable = None, **kwargs) -> None:
        """Aggiunge un comando alla coda da eseguire nel main thread."""
        with self._lock:
            self._pending_commands.append({
                "type": command_type,
                "callback": callback,
                "kwargs": kwargs,
            })

    def get_next_command(self) -> dict | None:
        """Estrae il prossimo comando dalla coda (thread-safe)."""
        with self._lock:
            if self._pending_commands:
                return self._pending_commands.pop(0)
            return None

    # --- Console Mode (deep sleep — zero WebApp) ---

    def set_console_mode(self, active: bool, hours: float | None = None) -> None:
        """Attiva/disattiva la modalità console (deep sleep).

        Args:
            active: True per attivare, False per disattivare.
            hours: Se specificato, auto-resume dopo N ore.
        """
        with self._lock:
            self._console_mode = active
            if active and hours:
                self._console_mode_until = datetime.now() + timedelta(hours=hours)
            else:
                self._console_mode_until = None

    def is_console_mode(self) -> bool:
        """Restituisce True se il bot è in modalità console."""
        with self._lock:
            if self._console_mode and self._console_mode_until:
                if datetime.now() >= self._console_mode_until:
                    self._console_mode = False
                    self._console_mode_until = None
            return self._console_mode

    def get_console_mode_until(self) -> datetime | None:
        """Restituisce il timestamp di auto-resume, o None."""
        with self._lock:
            return self._console_mode_until

    def has_commands(self) -> bool:
        """Controlla se ci sono comandi in coda."""
        with self._lock:
            return len(self._pending_commands) > 0

    # --- Aggiornamento statistiche ---

    def update_stats(self, cycle: int = 0, relisted: int = 0, failed: int = 0) -> None:
        """Aggiorna i contatori del bot e imposta il timestamp di scansione.

        Args:
            cycle: Numero di cicli da aggiungere (default 0). Azzera last_relisted/failed se > 0.
            relisted: Numero di listing relistati da aggiungere all'ultimo e al totale.
            failed: Numero di listing falliti da aggiungere all'ultimo e al totale.
        """
        with self._lock:
            if cycle > 0:
                self.cycle_count += cycle
                self.last_relisted = 0
                self.last_failed = 0
                
            self.last_relisted += relisted
            self.last_failed += failed
            self.total_relisted += relisted
            self.total_failed += failed
            
            if cycle > 0 or relisted > 0 or failed > 0:
                self.last_scan_time = datetime.now()
                
            # Se abbiamo appena fatto un relist con successo, impostiamo il flag
            if relisted > 0:
                self.last_relisted_by_bot = datetime.now()

    def get_seconds_since_last_relist_by_bot(self) -> float | None:
        """Restituisce i secondi dall'ultimo relist del bot, o None se mai fatto."""
        with self._lock:
            if self.last_relisted_by_bot is None:
                return None
            return (datetime.now() - self.last_relisted_by_bot).total_seconds()

    # --- Snapshot dello stato ---

    def get_status(self) -> dict[str, Any]:
        """Restituisce un dict con lo stato corrente del bot."""
        with self._lock:
            console_until = None
            if self._console_mode_until:
                console_until = self._console_mode_until.strftime("%H:%M")
            return {
                "paused": self._paused,
                "console_mode": self._console_mode,
                "console_until": console_until,
                "force_relist": self._force_relist,
                "cycle_count": self.cycle_count,
                "last_relisted": self.last_relisted,
                "last_failed": self.last_failed,
                "total_relisted": self.total_relisted,
                "total_failed": self.total_failed,
                "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            }

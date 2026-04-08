"""BotState — stato condiviso thread-safe per il bot di relist.

Fornisce un'interfaccia sicura per leggere e modificare lo stato del bot
da thread diversi (es. thread principale del bot + thread Telegram polling).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


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
    cycle_count: int = field(default=0)
    last_relisted: int = field(default=0)
    last_failed: int = field(default=0)
    last_scan_time: datetime | None = field(default=None)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Command queue for thread-safe operations
    _pending_commands: list[dict] = field(default_factory=list, repr=False)

    # --- Pause / Resume ---

    def set_paused(self, value: bool) -> None:
        """Imposta lo stato di pausa del bot."""
        with self._lock:
            self._paused = value

    def is_paused(self) -> bool:
        """Restituisce True se il bot è in pausa."""
        with self._lock:
            return self._paused

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

    def has_commands(self) -> bool:
        """Controlla se ci sono comandi in coda."""
        with self._lock:
            return len(self._pending_commands) > 0

    # --- Aggiornamento statistiche ---

    def update_stats(self, cycle: int = 0, relisted: int = 0, failed: int = 0) -> None:
        """Aggiorna i contatori del bot e imposta il timestamp di scansione.

        Args:
            cycle: Numero di cicli da aggiungere (default 0).
            relisted: Numero di listing relistati da aggiungere.
            failed: Numero di listing falliti da aggiungere.
        """
        with self._lock:
            self.cycle_count += cycle
            self.last_relisted += relisted
            self.last_failed += failed
            self.last_scan_time = datetime.now()

    # --- Snapshot dello stato ---

    def get_status(self) -> dict[str, Any]:
        """Restituisce un dict con lo stato corrente del bot."""
        with self._lock:
            return {
                "paused": self._paused,
                "force_relist": self._force_relist,
                "cycle_count": self.cycle_count,
                "last_relisted": self.last_relisted,
                "last_failed": self.last_failed,
                "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            }

"""Rate limiter for anti-detection delays.

Enforces configurable delay range with jitter between browser actions.
Follows the same _random_delay pattern as navigator.py.
"""
from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.config import RateLimitingConfig

logger = logging.getLogger(__name__)


class RateLimiter:
    """Gestisce i ritardi tra le azioni del browser per anti-detection.

    Supporta delay casuali (jitter) e delay minimi garantiti.
    """

    def __init__(self, min_delay_ms: int = 2000, max_delay_ms: int = 5000):
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self._last_action_time: float = 0
        self._last_delay_ms: int = 0

    @classmethod
    def from_config(cls, config: "RateLimitingConfig") -> "RateLimiter":
        """Crea RateLimiter da un RateLimitingConfig dataclass."""
        return cls(
            min_delay_ms=config.min_delay_ms,
            max_delay_ms=config.max_delay_ms,
        )

    @property
    def last_delay_ms(self) -> int:
        """Ritorna l'ultimo delay applicato (per logging)."""
        return self._last_delay_ms

    def wait(self) -> None:
        """Attendi un ritardo casuale tra min e max."""
        self._last_delay_ms = random.randint(self.min_delay_ms, self.max_delay_ms)
        delay_sec = self._last_delay_ms / 1000.0
        logger.debug(f"Rate limit: attesa {self._last_delay_ms}ms")
        time.sleep(delay_sec)
        self._last_action_time = time.monotonic()

    def wait_if_needed(self) -> None:
        """Attendi solo se non è passato abbastanza tempo dall'ultima azione."""
        if self._last_action_time == 0:
            self.wait()
            return

        elapsed_ms = (time.monotonic() - self._last_action_time) * 1000
        remaining_ms = self.min_delay_ms - elapsed_ms

        if remaining_ms > 0:
            self._last_delay_ms = int(remaining_ms)
            delay_sec = remaining_ms / 1000.0
            logger.debug(f"Rate limit: attesa rimanente {int(remaining_ms)}ms")
            time.sleep(delay_sec)
            self._last_action_time = time.monotonic()
        else:
            logger.debug("Rate limit: nessuna attesa necessaria")

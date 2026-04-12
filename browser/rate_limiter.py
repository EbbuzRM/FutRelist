"""Rate limiter for anti-detection delays.

Enforces configurable delay range with jitter between browser actions.
"""
from __future__ import annotations

import logging
import random
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Gestisce i ritardi tra le azioni del browser per anti-detection.

    Applica un delay casuale (jitter) nell'intervallo [min_delay_ms, max_delay_ms]
    ad ogni chiamata a wait().
    """

    def __init__(self, min_delay_ms: int = 2000, max_delay_ms: int = 5000):
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms

    def wait(self) -> None:
        """Attendi un ritardo casuale tra min e max."""
        delay_ms = random.randint(self.min_delay_ms, self.max_delay_ms)
        logger.debug(f"Rate limit: attesa {delay_ms}ms")
        time.sleep(delay_ms / 1000.0)

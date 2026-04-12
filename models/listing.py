"""Data model for transfer market listings.

Defines the types consumed by the detector (T03) and integration (T04).
No browser interaction — pure data model.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class ListingState(enum.Enum):
    """Stato di un listing sul transfer market."""

    ACTIVE = "active"       # attualmente sul mercato
    EXPIRED = "expired"     # non venduto, da rimettere in lista
    SOLD = "sold"           # venduto con successo
    UNKNOWN = "unknown"     # stato non determinabile


@dataclass
class PlayerListing:
    """Rappresenta un singolo player listing."""

    index: int                          # posizione nella lista (0-based)
    player_name: str                    # nome giocatore (es. "Mbappé")
    rating: Optional[int] = None        # overall rating (es. 91)
    position: Optional[str] = None      # posizione (es. "ST")
    state: ListingState = ListingState.UNKNOWN
    current_price: Optional[int] = None # prezzo Buy Now in coins
    start_price: Optional[int] = None   # prezzo partenza asta in coins
    time_remaining: Optional[str] = None  # tempo rimanente (es. "1h 5m")
    time_remaining_seconds: Optional[int] = None  # tempo rimanente in secondi

    @property
    def needs_relist(self) -> bool:
        """True se il listing è scaduto e va rimesso in vendita."""
        return self.state == ListingState.EXPIRED


@dataclass
class ListingScanResult:
    """Risultato di una scansione completa dei listing."""

    total_count: int
    active_count: int
    expired_count: int
    sold_count: int
    listings: list[PlayerListing] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True se non ci sono listing."""
        return len(self.listings) == 0

    @classmethod
    def empty(cls) -> ListingScanResult:
        """Crea un risultato vuoto (nessun listing)."""
        return cls(
            total_count=0,
            active_count=0,
            expired_count=0,
            sold_count=0,
            listings=[],
        )

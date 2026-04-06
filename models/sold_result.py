"""Data model for sold items cleanup results."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SoldCreditsResult:
    """Risultato della pulizia degli oggetti venduti.

    Attributes:
        total_credits: Totale crediti raccolti dagli oggetti venduti.
        items_cleared: Numero di oggetti cancellati.
        success: True se l'operazione è completata con successo.
        error: Messaggio di errore (None se successo).
    """

    total_credits: int = 0
    items_cleared: int = 0
    success: bool = True
    error: str | None = None

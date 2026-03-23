"""Data model for relist action results.

Tracks per-listing outcomes and batch aggregation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RelistResult:
    """Risultato di un singolo rilist action."""

    listing_index: int
    player_name: str
    old_price: int | None
    new_price: int | None
    success: bool
    error: str | None = None


@dataclass
class RelistBatchResult:
    """Risultato aggregato di un batch di rilist."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[RelistResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Percentuale di successo (0-100)."""
        if self.total == 0:
            return 0.0
        return (self.succeeded / self.total) * 100

    @classmethod
    def from_results(cls, results: list[RelistResult]) -> RelistBatchResult:
        """Crea un batch result da una lista di risultati individuali."""
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        return cls(
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            results=results,
        )

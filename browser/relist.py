"""Relist executor for FIFA 26 WebApp - price adjustment and relist actions."""
import logging

logger = logging.getLogger(__name__)


def calculate_adjusted_price(
    current_price: int,
    adjustment_type: str,
    adjustment_value: float,
    min_price: int = 200,
    max_price: int = 15_000_000,
) -> int:
    """Calcola il prezzo aggiustato per il rilist."""
    if adjustment_type == "percentage":
        adjusted = current_price * (1 + adjustment_value / 100)
    elif adjustment_type == "fixed":
        adjusted = current_price + adjustment_value
    else:
        logger.warning(f"Tipo aggiustamento sconosciuto: {adjustment_type}")
        return current_price
    return max(min_price, min(max_price, int(adjusted)))

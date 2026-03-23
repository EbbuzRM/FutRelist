"""Relist executor for FIFA 26 WebApp - price adjustment and relist actions."""
import logging

from playwright.sync_api import Page
from models.relist_result import RelistResult, RelistBatchResult
from browser.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SELECTORS = {
    "relist_button": 'button:has-text("Relist"), .relist-btn',
    "relist_all_button": 'button:has-text("Relist All"), .relist-all-btn',
    "price_input": 'input[type="number"], .price-input, .ut-price-input input',
    "confirm_button": 'button:has-text("Confirm"), button:has-text("Ok"), .btn-action',
    "listing_items": '.listFUTItem.player',
    "success_indicator": '.notification-success, .toast-success',
}


class RelistExecutor:
    """Esegue rilist automatici sui listing scaduti."""

    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        rate_limiting = config.get("rate_limiting", {})
        self.rate_limiter = RateLimiter(
            min_delay_ms=rate_limiting.get("min_delay_ms", 2000),
            max_delay_ms=rate_limiting.get("max_delay_ms", 5000),
        )
        # Price adjustment config
        defaults = config.get("listing_defaults", {})
        self.adjustment_type = defaults.get("price_adjustment_type", "percentage")
        self.adjustment_value = defaults.get("price_adjustment_value", 0)
        self.min_price = defaults.get("min_price", 200)
        self.max_price = defaults.get("max_price", 15_000_000)

    def handle_dialog(self, dialog):
        """Gestisce i dialog di conferma del WebApp - accetta automaticamente."""
        logger.info(f"Dialog rilevato: {dialog.message}")
        dialog.accept()

    def relist_single(self, listing) -> RelistResult:
        """Rilista un singolo listing scaduto.

        Flow: click relist → check price input → fill if present → click confirm → handle dialog.
        Ritorna RelistResult con esito.
        """
        try:
            logger.info(f"Rilistando [{listing.index}] {listing.player_name}...")

            # Register dialog handler BEFORE clicking (Playwright requirement)
            self.page.on("dialog", self.handle_dialog)

            # Get the listing element by index
            listing_el = self.page.locator(SELECTORS["listing_items"]).nth(listing.index)
            relist_btn = listing_el.locator(SELECTORS["relist_button"])

            # Click relist
            relist_btn.click()
            self.page.wait_for_timeout(2000)

            # Check if price input appeared (individual relist mode)
            price_input = self.page.query_selector(SELECTORS["price_input"])
            new_price = None

            if price_input and listing.current_price:
                new_price = calculate_adjusted_price(
                    listing.current_price,
                    self.adjustment_type,
                    self.adjustment_value,
                    min_price=self.min_price,
                    max_price=self.max_price,
                )
                logger.info(f"  Prezzo: {listing.current_price} → {new_price}")
                price_input.fill(str(new_price))

                # Click confirm button
                confirm_btn = self.page.query_selector(SELECTORS["confirm_button"])
                if confirm_btn:
                    confirm_btn.click()
                    self.page.wait_for_timeout(1500)

            self.rate_limiter.wait()

            logger.info(f"  Rilist completato: {listing.player_name}")
            return RelistResult(
                listing_index=listing.index,
                player_name=listing.player_name,
                old_price=listing.current_price,
                new_price=new_price or listing.current_price,
                success=True,
            )

        except Exception as e:
            logger.error(f"  Errore rilistando {listing.player_name}: {e}")
            return RelistResult(
                listing_index=listing.index,
                player_name=listing.player_name,
                old_price=listing.current_price,
                new_price=None,
                success=False,
                error=str(e),
            )

    def relist_expired(self, expired_listings) -> RelistBatchResult:
        """Rilista tutti i listing scaduti con rate limiting.

        Ritorna RelistBatchResult aggregato.
        """
        if not expired_listings:
            logger.info("Nessun listing scaduto da rilistare")
            return RelistBatchResult.from_results([])

        logger.info(f"Inizio rilist di {len(expired_listings)} listing scaduti...")
        results = []

        for listing in expired_listings:
            result = self.relist_single(listing)
            results.append(result)

        batch = RelistBatchResult.from_results(results)
        logger.info(
            f"Rilist completato: {batch.succeeded}/{batch.total} successi "
            f"({batch.success_rate:.1f}%)"
        )
        return batch


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

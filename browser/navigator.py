"""
Navigazione Transfer Market FIFA 26 WebApp - Dalla home alla Transfer List
"""
import logging
from playwright.sync_api import Page

from browser.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SELECTORS = {
    "transfers_nav": 'button:has-text("Transfers"), .icon-transfer',
    "transfer_list_tab": 'button:has-text("Transfer List"), .ut-tile-transfer-list',
    "my_listings_view": '.ut-transfer-list-view, .sectioned-item-list',
    "loading_indicator": '.ut-loading-spinner, .loading',
}


class TransferMarketNavigator:
    """Naviga dalla Home alla vista Transfer List (My Listings) nel WebApp FIFA 26."""

    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        rate_limiting = config.get("rate_limiting", {})
        self.rate_limiter = RateLimiter(
            min_delay_ms=rate_limiting.get("min_delay_ms", 2000),
            max_delay_ms=rate_limiting.get("max_delay_ms", 5000),
        )

    def go_to_transfer_list(self) -> bool:
        """Naviga dalla Home alla vista Transfer List.

        Ritorna True se la navigazione ha successo, False altrimenti.
        """
        try:
            logger.info("Inizio navigazione verso Transfer List...")

            # Step 1: Clicca il pulsante Transfers nella sidebar
            transfers_btn = self.page.query_selector(SELECTORS["transfers_nav"])
            if transfers_btn is None:
                logger.error("Pulsante Transfers non trovato nella sidebar")
                return False

            logger.info("Clic su Transfers...")
            transfers_btn.click()
            self.page.wait_for_timeout(3000)
            self.rate_limiter.wait()

            # Step 2: Clicca il tab Transfer List
            transfer_list_btn = self.page.query_selector(SELECTORS["transfer_list_tab"])
            if transfer_list_btn is None:
                logger.error("Tab Transfer List non trovato")
                return False

            logger.info("Clic su Transfer List...")
            transfer_list_btn.click()
            self.page.wait_for_timeout(3000)
            self.rate_limiter.wait()

            # Step 3: Attendi che la vista sia pronta
            logger.info("Attesa caricamento vista...")
            self.page.wait_for_load_state("networkidle", timeout=15000)
            self.page.wait_for_selector(
                SELECTORS["my_listings_view"], state="visible", timeout=10000
            )

            logger.info("Transfer List caricata con successo")
            return True

        except Exception as e:
            logger.error(f"Errore durante navigazione verso Transfer List: {e}")
            return False

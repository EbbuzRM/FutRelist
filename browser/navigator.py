"""
Navigazione Transfer Market FIFA 26 WebApp - Dalla home alla Transfer List
"""
import logging
import random
from typing import Optional
from playwright.sync_api import Page

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
        self.min_delay_ms = rate_limiting.get("min_delay_ms", 2000)
        self.max_delay_ms = rate_limiting.get("max_delay_ms", 5000)

    def _random_delay(self, min_ms: Optional[int] = None, max_ms: Optional[int] = None) -> None:
        """Genera un ritardo casuale per resistenza al rilevamento bot."""
        min_val = min_ms if min_ms is not None else self.min_delay_ms
        max_val = max_ms if max_ms is not None else self.max_delay_ms
        delay = random.randint(min_val, max_val)
        logger.debug(f"Attesa casuale: {delay}ms")
        self.page.wait_for_timeout(delay)

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
            self._random_delay()

            # Step 2: Clicca il tab Transfer List
            transfer_list_btn = self.page.query_selector(SELECTORS["transfer_list_tab"])
            if transfer_list_btn is None:
                logger.error("Tab Transfer List non trovato")
                return False

            logger.info("Clic su Transfer List...")
            transfer_list_btn.click()
            self.page.wait_for_timeout(3000)
            self._random_delay()

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

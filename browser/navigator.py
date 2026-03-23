"""
Navigazione Transfer Market FIFA 26 WebApp - Dalla home alla Transfer List
"""
import logging
from playwright.sync_api import Page

from browser.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


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

            # Step 1: Clicca il pulsante Transfers nella sidebar navigation
            # Usa get_by_role che funziona con la WebApp React
            transfers_btn = self.page.get_by_role("button", name="Transfers")
            if not transfers_btn.count():
                # Prova con spazio prima (la WebApp mette uno spazio icon)
                transfers_btn = self.page.get_by_role("button", name=" Transfers")

            if not transfers_btn.count():
                logger.error("Pulsante Transfers non trovato nella sidebar")
                return False

            transfers_btn.first.click()
            logger.info("Clic su Transfers")
            self.page.wait_for_timeout(3000)
            self.rate_limiter.wait()

            # Step 2: Clicca l'area Transfer List
            transfer_list_area = self.page.get_by_role("heading", name="Transfer List")
            if not transfer_list_area.count():
                logger.error("Transfer List non trovato")
                return False

            transfer_list_area.first.click()
            logger.info("Clic su Transfer List")
            self.page.wait_for_timeout(3000)
            self.rate_limiter.wait()

            # Step 3: Verifica che siamo nella vista Transfer List
            heading = self.page.get_by_role("heading", name="Transfer List")
            if heading.count():
                logger.info("Transfer List caricata con successo")
                return True

            logger.warning("Transfer List potrebbe non essere caricata")
            return True

        except Exception as e:
            logger.error(f"Errore navigazione: {e}")
            return False

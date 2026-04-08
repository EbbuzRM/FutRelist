"""SoldHandler — gestione pulizia oggetti venduti dal Transfer Market.

Naviga alla pagina Sold Items, raccoglie i crediti totali dagli oggetti
venduti e li cancella per liberare spazio nella lista.

Segue i pattern esistenti: get_by_role selectors, RateLimiter, logging italiano.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from playwright.sync_api import Page

from browser.rate_limiter import RateLimiter
from models.sold_result import SoldCreditsResult

logger = logging.getLogger(__name__)

# Selettori per gli elementi DOM della pagina Sold Items
SELECTORS = {
    "sold_items_tab": "Sold Items",  # get_by_role heading name
    "sold_items_tab_it": "Oggetti venduti",  # versione italiana
    "clear_sold_items": "Clear Sold Items",  # get_by_role button name
    "clear_sold_items_it": "Cancella oggetti venduti",  # versione italiana
    "sold_item_price": ".auctionValue, .auction-value, .coins",  # selettore CSS prezzi
}


class SoldHandler:
    """Gestisce la navigazione e la pulizia degli oggetti venduti.

    Args:
        page: Playwright page object.
        config: Config dict con rate_limiting settings.
    """

    def __init__(self, page: Page, config: dict[str, Any]):
        self.page = page
        self.config = config
        rate_limiting = config.get("rate_limiting", {})
        self.rate_limiter = RateLimiter(
            min_delay_ms=rate_limiting.get("min_delay_ms", 2000),
            max_delay_ms=rate_limiting.get("max_delay_ms", 5000),
        )

    def process_sold_items(self) -> SoldCreditsResult:
        """Flusso completo: naviga, raccogli crediti, cancella venduti.

        Returns:
            SoldCreditsResult con total_credits, items_cleared, success, error.
        """
        try:
            # Step 1: Naviga alla pagina Sold Items
            logger.info("Inizio pulizia oggetti venduti...")
            if not self._navigate_to_sold_items():
                logger.error("Navigazione a Sold Items fallita")
                return SoldCreditsResult(
                    success=False,
                    error="Navigazione a Sold Items fallita",
                )

            # Step 2: Raccogli i crediti dagli oggetti venduti
            total_credits, items_count = self._collect_sold_credits()

            if items_count == 0:
                logger.info("Nessun oggetto venduto da cancellare")
                return SoldCreditsResult(
                    total_credits=0,
                    items_cleared=0,
                    success=True,
                )

            logger.info(f"Trovati {items_count} oggetti venduti per {total_credits:,} crediti totali")

            # Step 3: Cancella gli oggetti venduti
            if not self._clear_sold_items():
                logger.error("Cancellazione oggetti venduti fallita")
                return SoldCreditsResult(
                    total_credits=total_credits,
                    items_cleared=0,
                    success=False,
                    error="Cancellazione oggetti venduti fallita",
                )

            logger.info(f"Pulizia completata: {items_count} oggetti, {total_credits:,} crediti raccolti")
            return SoldCreditsResult(
                total_credits=total_credits,
                items_cleared=items_count,
                success=True,
            )

        except Exception as e:
            logger.error(f"Errore durante la pulizia degli oggetti venduti: {e}")
            return SoldCreditsResult(
                success=False,
                error=str(e),
            )

    def _navigate_to_sold_items(self) -> bool:
        """Naviga alla sezione Sold Items nella Transfer List.

        Percorso: Transfers → Transfer List → (ella pagina stessa) Sold section

        Returns True se la navigazione ha successo.
        """
        try:
            logger.info("Navigazione verso Sold Items...")

            # Step 1: Clicca Transfers nella sidebar
            transfers_btn = self.page.get_by_role("button", name="Transfers")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name=" Transfers")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name="Trasferimenti")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name=" Trasferimenti")

            if not transfers_btn.count():
                logger.error("Pulsante Transfers non trovato")
                return False

            transfers_btn.first.click()
            logger.info("Clic su Transfers (sidebar)")
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait()

            # Step 2: Clicca Transfer List heading
            transfer_list = self.page.get_by_role("heading", name="Transfer List")
            if not transfer_list.count():
                transfer_list = self.page.get_by_role("heading", name="Lista trasferimenti")

            if not transfer_list.count():
                logger.error("Transfer List non trovato")
                return False

            transfer_list.first.click()
            logger.info("Clic su Transfer List")
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait()

            # Step 3: Nella Transfer List, cerca e clicca "Sold" tab/heading
            sold_tab = self.page.get_by_role("heading", name="Sold")
            if not sold_tab.count():
                sold_tab = self.page.get_by_role("heading", name="Venduti")
            if not sold_tab.count():
                sold_tab = self.page.get_by_role("heading", name="Sold Items")
            if not sold_tab.count():
                sold_tab = self.page.get_by_role("heading", name="Oggetti venduti")
            if not sold_tab.count():
                # Prova come button/tab
                sold_tab = self.page.get_by_role("button", name="Sold")
            if not sold_tab.count():
                sold_tab = self.page.get_by_role("button", name="Venduti")

            if not sold_tab.count():
                logger.error("Tab Sold non trovato nella Transfer List")
                return False

            sold_tab.first.click()
            logger.info("Clic su Sold")
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait()

            logger.info("Navigazione a Sold completata")
            return True

        except Exception as e:
            logger.error(f"Errore navigazione Sold Items: {e}")
            return False

    def _collect_sold_credits(self) -> tuple[int, int]:
        """Raccoglie i prezzi degli oggetti venduti dal DOM.

        Scansiona gli elementi prezzo nella pagina Sold Items,
        parsifica i valori in coins e restituisce il totale.

        Returns:
            Tuple di (total_credits, items_count).
        """
        try:
            raw_items = self.page.eval_on_selector_all(
                SELECTORS["sold_item_price"],
                """els => els.map(el => ({
                    price: el.textContent.trim()
                }))""",
            )

            total_credits = 0
            items_count = 0

            for item in raw_items:
                price_text = item.get("price", "")
                price = self._parse_coin_value(price_text)
                if price is not None:
                    total_credits += price
                    items_count += 1

            return total_credits, items_count

        except Exception as e:
            logger.warning(f"Errore nella raccolta crediti: {e}")
            return 0, 0

    def _clear_sold_items(self) -> bool:
        """Clicca il pulsante 'Clear Sold Items'.

        Returns True se il click è avvenuto con successo.
        """
        try:
            # Prova prima con get_by_role (più robusto)
            clear_btn = self.page.get_by_role("button", name="Clear Sold Items")
            if not clear_btn.count():
                clear_btn = self.page.get_by_role("button", name="Cancella oggetti venduti")
            if not clear_btn.count():
                # Prova con selector CSS generico
                clear_btn = self.page.locator('button:has-text("Clear Sold"), button:has-text("Cancella")')
            
            if not clear_btn.count():
                logger.warning("Pulsante Clear Sold Items non trovato")
                return False

            clear_btn.first.click()
            logger.info("Clic su Clear Sold Items")
            self.rate_limiter.wait()

            # Gestisci eventuale dialog di conferma
            self._handle_clear_dialog()

            return True

        except Exception as e:
            logger.error(f"Errore nella cancellazione oggetti venduti: {e}")
            return False

    def _handle_clear_dialog(self) -> None:
        """Gestisce il dialog di conferma per la cancellazione.

        Cerca e clicca il pulsante di conferma se appare un dialog.
        """
        try:
            # Prova vari testi per il pulsante di conferma
            confirm_labels = ["Confirm", "Conferma", "OK", "Ok", "Yes", "Sì"]
            for label in confirm_labels:
                btn = self.page.get_by_role("button", name=label)
                if btn.count() and btn.first.is_visible(timeout=2000):
                    btn.first.click()
                    logger.info(f"Dialog confermato: clic su '{label}'")
                    self.rate_limiter.wait()
                    return
        except Exception:
            # Nessun dialog trovato — va bene così
            pass

    # --- Helper methods ---

    @staticmethod
    def _parse_coin_value(text: str) -> int | None:
        """Parsa un valore in coins da una stringa.

        Esempi:
            '10,000 coins' → 10000
            '500' → 500
            'invalid' → None
        """
        if not text:
            return None
        digits = re.sub(r'[^\d]', '', text)
        if digits:
            return int(digits)
        return None

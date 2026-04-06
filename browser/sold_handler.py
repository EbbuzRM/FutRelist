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
        """Naviga: Home → Transfers → Sold Items.

        Segue il pattern di TransferMarketNavigator.go_to_transfer_list().
        Returns True se la navigazione ha successo.
        """
        try:
            logger.info("Navigazione verso Sold Items...")

            # Step 1: Clicca Transfers nella sidebar
            transfers_btn = self._find_button("Transfers", "Trasferimenti")
            if not transfers_btn:
                logger.error("Pulsante Transfers non trovato")
                return False

            transfers_btn.click()
            logger.info("Clic su Transfers")
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait()

            # Step 2: Clicca Sold Items tab
            sold_tab = self._find_button(
                SELECTORS["sold_items_tab"],
                SELECTORS["sold_items_tab_it"],
            )
            if not sold_tab:
                # Prova come heading (alcune versioni EA usano heading clickable)
                sold_tab = self._find_heading(SELECTORS["sold_items_tab"])
                if not sold_tab:
                    sold_tab = self._find_heading(SELECTORS["sold_items_tab_it"])

            if not sold_tab:
                logger.error("Tab Sold Items non trovato")
                return False

            sold_tab.click()
            logger.info("Clic su Sold Items")
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait()

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
            clear_btn = self._find_button(
                SELECTORS["clear_sold_items"],
                SELECTORS["clear_sold_items_it"],
            )
            if not clear_btn:
                logger.warning("Pulsante Clear Sold Items non trovato")
                return False

            clear_btn.click()
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

    def _find_button(self, name_en: str, name_it: str = "") -> Any | None:
        """Cerca un pulsante per nome (inglese e italiano)."""
        for name in [name_en, name_it]:
            if not name:
                continue
            try:
                btn = self.page.get_by_role("button", name=name)
                if btn.count() and btn.first.is_visible():
                    return btn.first
            except Exception:
                continue
        return None

    def _find_heading(self, name: str) -> Any | None:
        """Cerca un heading per nome."""
        try:
            heading = self.page.get_by_role("heading", name=name)
            if heading.count() and heading.first.is_visible():
                return heading.first
        except Exception:
            pass
        return None

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

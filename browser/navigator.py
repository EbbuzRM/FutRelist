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

    def dismiss_popups(self) -> None:
        """Chiude eventuali popup/modale EA (es. 'Message from the FC Team') cliccando Continue.

        Cerca tutti i possibili pulsanti di dismissione in inglese e italiano.
        Non lancia eccezioni: se non trova nulla, prosegue in silenzio.
        """
        # Lista di testi che identificano pulsanti di dismissione comune nei popup EA
        dismiss_labels = ["Continue", "Continua", "Ok", "OK", "Close", "Chiudi", "Got It", "Ho capito"]
        
        for label in dismiss_labels:
            try:
                btn = self.page.get_by_role("button", name=label)
                if btn.count() and btn.first.is_visible():
                    logger.info(f"Popup rilevato. Click su '{label}' per chiuderlo...")
                    btn.first.click()
                    self.page.wait_for_timeout(1500)
                    # Controlla se ci sono ulteriori popup in cascata (es. 1/2, 2/2)
                    # Riesegue il check fino a 3 volte per smaltire messaggi multipli
                    for _ in range(2):
                        btn2 = self.page.get_by_role("button", name=label)
                        if btn2.count() and btn2.first.is_visible():
                            btn2.first.click()
                            self.page.wait_for_timeout(1500)
                        else:
                            break
                    break  # Uscito dal loop label se ha trovato e cliccato
            except Exception:
                continue  # Tenta il label successivo

    def go_to_transfer_list(self, fast: bool = False) -> bool:
        """Naviga dalla Home alla vista Transfer List.

        Args:
            fast: Se True, usa delay ridotti (1-2s invece di 2-5s) per golden retry.

        Ritorna True se la navigazione ha successo, False altrimenti.
        """
        try:
            logger.info("Inizio navigazione verso Transfer List...")

            # Step 0: Chiudi eventuali popup/annunci EA prima di navigare
            self.dismiss_popups()

            # Step 0b: Dismiss any blocking modal overlay (e.g. form-modal, view-modal)
            # These intercept clicks even when no button is visible
            try:
                modal = self.page.query_selector('.view-modal-container, .ea-dialog-view, .form-modal')
                if modal and modal.is_visible():
                    logger.info("Modale bloccante rilevata. Press Escape per chiuderla...")
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(1000)
                    # Verify modal is gone
                    modal2 = self.page.query_selector('.view-modal-container, .ea-dialog-view, .form-modal')
                    if modal2 and modal2.is_visible():
                        logger.warning("Modale ancora presente dopo Escape, secondo tentativo...")
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(1000)
            except Exception as e:
                logger.debug(f"Check modale fallito: {e}")

            # Step 1: Clicca il pulsante Transfers nella sidebar navigation
            transfers_btn = self.page.get_by_role("button", name="Transfers")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name=" Transfers")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name="Trasferimenti")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name=" Trasferimenti")

            if not transfers_btn.count():
                logger.error("Pulsante Transfers non trovato nella sidebar")
                return False

            transfers_btn.first.click()
            logger.info("Clic su Transfers")
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait_fast() if fast else self.rate_limiter.wait()

            # Step 1b: Dismiss any popup that appeared after clicking Transfers
            # EA often shows popups (announcements, notifications) after navigation
            self.dismiss_popups()
            # Also try Escape to dismiss any blocking modal overlay
            try:
                modal = self.page.query_selector('.view-modal-container, .ea-dialog-view, .form-modal')
                if modal and modal.is_visible():
                    logger.info("Modale EA apparso dopo click Transfers. Chiudo con Escape...")
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(1000)
                    # Retry dismiss in case Escape revealed a button
                    self.dismiss_popups()
            except Exception:
                pass

            # Step 2: Clicca l'area Transfer List
            # Retry up to 3 times if popup intercepts the click
            transfer_list_clicked = False
            for attempt in range(3):
                transfer_list_area = self.page.get_by_role("heading", name="Transfer List")
                if not transfer_list_area.count():
                    logger.error("Transfer List non trovato")
                    return False

                try:
                    transfer_list_area.first.click(timeout=10000)
                    transfer_list_clicked = True
                    logger.info("Clic su Transfer List")
                    break
                except Exception as click_err:
                    if "intercepts pointer events" in str(click_err) or "timeout" in str(click_err).lower():
                        logger.warning(f"Click Transfer List bloccato (tentativo {attempt+1}/3), dismiss popup...")
                        self.dismiss_popups()
                        # Try Escape for stubborn modals
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(1000)
                        self.dismiss_popups()
                    else:
                        raise

            if not transfer_list_clicked:
                logger.error("Impossibile cliccare Transfer List dopo 3 tentativi")
                return False

            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait_fast() if fast else self.rate_limiter.wait()

            # Step 3: Verifica che il contenuto della Transfer List sia effettivamente caricato.
            # Controllare di nuovo l'heading non basta (era già lì dal passo precedente).
            # Aspettiamo il container o i listing oppure lo stato vuoto.
            try:
                self.page.wait_for_selector(
                    '.ut-transfer-list-view, .listFUTItem, .no-items, .empty-list',
                    timeout=5000,
                )
                logger.info("Transfer List caricata con successo")
                return True
            except Exception:
                # Il selettore non è garantito su tutti i client/versioni EA:
                # se timeout, tentiamo comunque (potrebbe essere già visibile)
                logger.warning("Transfer List potrebbe non essere caricata (timeout attesa contenuto)")
                return True

        except Exception as e:
            logger.error(f"Errore navigazione: {e}")
            return False


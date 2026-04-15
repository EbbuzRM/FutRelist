"""Relist executor for FIFA 26 WebApp - price adjustment and relist actions."""
import logging

from playwright.sync_api import Page
from models.relist_result import RelistResult, RelistBatchResult
from browser.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SELECTORS = {
    "relist_button": 'button:has-text("Relist"), button:has-text("Rilista"), .relist-btn',
    "relist_all_button": 'button:has-text("Re-list All"), button:has-text("Relist All"), button:has-text("Rilista tutto"), button:has-text("Rilista Tutto"), .relist-all-btn',
    "confirm_yes": 'button:has-text("Yes"), button:has-text("Sì"), button:has-text("Si"), .btn-standard.call-to-action',
    "duration_button": 'button:has-text("{duration}"), .duration-option:has-text("{duration}")',
    "price_input": 'input[type="number"], .price-input, .ut-price-input input',
    "confirm_button": 'button:has-text("Confirm"), button:has-text("Ok"), .btn-action',
    "listing_items": '.listFUTItem',
    "error_banner": '[class*="error"], [class*="Error"], .ut-messaging-viewError, .error-message, .message--error',
    "error_text": 'could not be re-listed,could not be listed,error,failed',
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
        defaults = config.get("listing_defaults", {})
        self.relist_mode = defaults.get("relist_mode", "per_listing")
        self.duration = defaults.get("duration", "3h").upper()
        self.adjustment_type = defaults.get("price_adjustment_type", "percentage")
        self.adjustment_value = defaults.get("price_adjustment_value", 0)
        self.min_price = defaults.get("min_price", 200)
        self.max_price = defaults.get("max_price", 15_000_000)

    def _click_relist_button(self, listing_index: int) -> None:
        listing_el = self.page.locator(SELECTORS["listing_items"]).nth(listing_index)
        listing_el.locator(SELECTORS["relist_button"]).click()
        self.page.wait_for_timeout(2000)

    def _select_duration_if_prompted(self) -> None:
        selector = SELECTORS["duration_button"].format(duration=self.duration)
        duration_btn = self.page.locator(selector).first
        if duration_btn.is_visible():
            duration_btn.click()
            self.page.wait_for_timeout(1000)

    def _fill_price_if_present(self, current_price: int) -> int | None:
        price_input = self.page.locator(SELECTORS["price_input"]).first
        if not price_input.is_visible() or not current_price:
            return None

        new_price = calculate_adjusted_price(
            current_price, self.adjustment_type, self.adjustment_value,
            min_price=self.min_price, max_price=self.max_price,
        )
        price_input.fill(str(new_price))

        confirm_btn = self.page.locator(SELECTORS["confirm_button"]).first
        if confirm_btn.is_visible():
            confirm_btn.click()
            self.page.wait_for_timeout(1500)

        return new_price

    def relist_single(self, listing) -> RelistResult:
        """Rilista un singolo listing scaduto. Ritorna RelistResult con esito."""
        try:
            # Nota: EA usa modal HTML, non browser dialog nativi.
            # page.once("dialog") non viene mai consumato e accumulerebbe handler stale.
            self._click_relist_button(listing.index)
            self._select_duration_if_prompted()
            new_price = self._fill_price_if_present(listing.current_price)
            self.rate_limiter.wait()

            return RelistResult(
                listing_index=listing.index, player_name=listing.player_name,
                old_price=listing.current_price, new_price=new_price or listing.current_price,
                success=True,
            )
        except Exception as e:
            return RelistResult(
                listing_index=listing.index, player_name=listing.player_name,
                old_price=listing.current_price, new_price=None,
                success=False, error=str(e),
            )

    def relist_all(self, count: int = 1) -> RelistBatchResult:
        """Clicca 'Re-list All' e auto-accetta la modale di conferma HTML."""
        try:
            # Usiamo locator per resilienza al DOM
            relist_all_btn = self.page.locator(SELECTORS["relist_all_button"]).first
            
            if not relist_all_btn.is_visible():
                logger.info("Bottone 'Re-list All' non visibile (nessun listing scaduto?)")
                return RelistBatchResult.from_results([])

            # Il click su locator ha auto-retry se l'elemento si distacca o è coperto momentaneamente
            relist_all_btn.click()
            logger.info(f"Cliccato 'Re-list All' per {count} oggetti, attesa modale di conferma...")

            # Attende e clicca il 'Yes' della modale
            try:
                confirm_btn = self.page.locator(SELECTORS["confirm_yes"]).first
                # Aspettiamo esplicitamente che sia visibile per evitare race conditions
                confirm_btn.wait_for(state="visible", timeout=5000)
                confirm_btn.click()
                logger.info("Modale di conferma accettata (Yes cliccato)")
            except Exception as e:
                logger.debug(f"Nessuna modale di conferma cliccata o errore: {e}")

            # Attesa breve per stabilizzazione UI dopo chiusura modale,
            # poi rate_limiter aggiunge il delay anti-bot configurato
            self.page.wait_for_timeout(1500)
            self.rate_limiter.wait()

            # Attesa per stabilizzazione UI
            self.page.wait_for_timeout(2000)

            # Verifica errori post-relist (banner-level)
            relist_error = self._check_relist_errors()
            if relist_error:
                logger.error(f"Errore post-relist rilevato: {relist_error}")
                batch_result = RelistBatchResult.from_results([
                    RelistResult(
                        listing_index=-1, player_name="ALL",
                        old_price=None, new_price=None, success=False, error=relist_error,
                    )
                ])
                batch_result.relist_error = relist_error
                return batch_result

            logger.info(f"Re-list All completato per {count} oggetti")
            # NOTA: non possiamo sapere qui quanti siano effettivamente riusciti.
            # Il conteggio reale viene calcolato in main.py tramite scan post-relist.
            # Creiamo risultati placeholder — saranno sovrascritti con i conteggi verificati.
            batch_result = RelistBatchResult.from_results([])
            batch_result.relist_error = None
            return batch_result
        except Exception as e:
            logger.error(f"Errore Re-list All: {e}")
            error_msg = str(e)
            batch_result = RelistBatchResult.from_results([
                RelistResult(
                    listing_index=-1, player_name="ALL",
                    old_price=None, new_price=None, success=False, error=error_msg,
                )
            ])
            batch_result.relist_error = error_msg
            return batch_result

    def _check_relist_errors(self) -> str | None:
        """Controlla errori banner post-relist nel DOM. Ritorna messaggio errore se presente."""
        try:
            error_selectors = [
                SELECTORS["error_banner"],
                '.ut-messaging-view[class*="error"]',
                '.message-container',
                '[data-ea-error="true"]',
            ]
            for sel in error_selectors:
                try:
                    el = self.page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        text = el.inner_text().lower()
                        if any(err in text for err in SELECTORS["error_text"].split(',')):
                            return text.strip()[:100]
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def check_session_valid(self) -> bool:
        """Verifica se la sessione è ancora valida dopo relist."""
        try:
            from browser.auth import AuthManager
            auth = AuthManager(self.config)
            if not auth.is_logged_in(self.page, timeout_ms=5000):
                logger.warning("Sessione non più valida rilevata post-relist")
                return False
            if auth.is_console_session_active(self.page):
                logger.warning("Sessione console attiva rilevata post-relist")
                return False
            return True
        except Exception as e:
            logger.debug(f"Errore check session: {e}")
            return True


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

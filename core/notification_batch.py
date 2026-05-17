import os
import tempfile
from datetime import datetime

from models.listing import ListingScanResult
from notifier import send_telegram_photo


class NotificationBatch:
    """
    Aggrega le statistiche di rilist per inviare notifiche Telegram batch,
    evitando di spammare l'utente a ogni singolo ciclo.
    Il flush è determinato da `is_ready_to_flush(current_wait)`: quando il
    prossimo wait è lungo (> batch_window), significa che l'ondata e' finita.
    """

    TRANSFER_LIST_CAPACITY = 100

    def __init__(self, batch_window_seconds: int = 120, max_cycles: int = 5):
        self.batch_window_seconds = batch_window_seconds
        self.max_cycles = max_cycles
        self.relisted = 0
        self.failed = 0
        self.cycles = 0
        self.expired_detected = 0
        self.last_flush_time: datetime | None = None

    def accumulate(self, scan: ListingScanResult, succeeded: int, failed: int, expired_count: int = 0):
        """Aggiunge i risultati di un ciclo all'accumulatore.

        expired_detected rappresenta gli oggetti realmente emersi nel batch:
        usa il totale processato come base, senza sommare scansioni duplicate.
        """
        self.relisted += succeeded
        self.failed += failed
        self.cycles += 1
        detected = expired_count if expired_count > 0 else (succeeded + failed)
        processed = self.relisted + self.failed
        self.expired_detected = min(max(self.expired_detected, detected, processed), self.TRANSFER_LIST_CAPACITY)

    def is_ready_to_flush(self, current_wait: int) -> bool:
        """
        Determina se e' il momento di inviare la notifica.
        Flush se:
        1. C'e' stata attivita' (rilist riusciti o fallimenti)
        2. E si verifica una delle condizioni di flush:
           - Il prossimo wait e' lungo (> batch_window), quindi abbiamo finito una 'ondata'
           - Abbiamo raggiunto il numero massimo di cicli
           - E' trascorso piu' di batch_window_seconds dall'ultimo flush
        """
        if self.cycles == 0:
            return False

        # Evita notifiche se non e' successo nulla (nessun rilist e nessun fallimento)
        if self.relisted == 0 and self.failed == 0:
            return False

        # Se il bot sta per dormire a lungo, invia subito il report dell'ondata appena conclusa
        if current_wait > self.batch_window_seconds:
            return True

        # Se abbiamo fatto troppi cicli rapidi, flush per dare feedback
        if self.cycles >= self.max_cycles:
            return True

        # Flush se e' gia' passato batch_window_seconds dall'ultimo report,
        # cosi' l'utente riceve aggiornamenti anche durante ondate lunghe a cicli rapidi.
        if self.last_flush_time is not None:
            elapsed = (datetime.now() - self.last_flush_time).total_seconds()
            if elapsed >= self.batch_window_seconds:
                return True

        return False

    def flush_if_any(
        self,
        app_config,
        page,
        logger,
        scan: ListingScanResult | None = None,
        last_relist_error: str | None = None,
        force: bool = False,
    ):
        """Invia il report se c'e' stata attivita' e le condizioni di flush sono soddisfatte.

        Args:
            force: Se True, forza il flush indipendentemente dalle condizioni (usato per shutdown/reboot).
        """
        if self.cycles == 0:
            return

        if not force and not self.is_ready_to_flush(0):
            return

        if not app_config.notifications.telegram_token or not app_config.notifications.telegram_chat_id:
            logger.warning("Skip notifica: token o chat_id mancante")
            self.reset()
            return

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            screenshot_path = tmp.name

        try:
            rilistati = self.relisted
            totale_oggetti = scan.total_count if scan else 0

            screenshot_taken = False
            if page:
                try:
                    if "signin.ea.com" in page.url.lower():
                        logger.warning("Skip screenshot: pagina di login (sicurezza credenziali)")
                    else:
                        page.screenshot(path=screenshot_path)
                        screenshot_taken = True
                except Exception as screenshot_err:
                    logger.warning(f"Screenshot fallito: {screenshot_err}")

            error_msg = f" \u26a0\ufe0f Error: {last_relist_error}" if last_relist_error else ""

            msg = (
                f"\U0001f514 Report Relist\n"
                f"-------------------\n"
                f"\U0001f4e6 Cicli totali: {self.cycles}\n"
                f"\U0001f4cb Totale oggetti: {totale_oggetti}\n"
                f"\u23f0 Scaduti rilevati: {self.expired_detected}\n"
                f"\U0001f680 Relistati: {rilistati}\n"
                f"\u274c Falliti: {self.failed}{error_msg}\n"
                f"\U0001f552 Modalita': \u26bd Relist Ibrido"
            )

            if screenshot_taken:
                send_telegram_photo(app_config.notifications, screenshot_path, msg)
            else:
                from notifier import send_telegram_alert

                send_telegram_alert(app_config.notifications, msg)
            logger.info(f"Notifica inviata: {self.relisted} rilistati, {self.failed} falliti.")

        except Exception as e:
            logger.error(f"Errore invio notifica: {e}")
        finally:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            self.reset()

    # Alias per compatibilita'
    def flush(
        self,
        app_config,
        page,
        logger,
        scan: ListingScanResult | None = None,
        last_relist_error: str | None = None,
        force: bool = False,
    ):
        """Flush standard — ora chiama flush_if_any per compatibilita'."""
        self.flush_if_any(app_config, page, logger, scan, last_relist_error, force=force)

    def reset(self):
        """Resetta i contatori del batch."""
        self.relisted = 0
        self.failed = 0
        self.cycles = 0
        self.expired_detected = 0
        self.last_flush_time = datetime.now()

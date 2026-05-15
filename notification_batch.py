import os
import tempfile
from datetime import datetime

from models.listing import ListingScanResult
from notifier import send_telegram_photo


class NotificationBatch:
    """
    Aggrega le statistiche di rilist per inviare notifiche Telegram batch,
    evitando di spammare l'utente a ogni singolo ciclo.
    """

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

        expired_detected usa expired_count se fornito (scansione pre-relist),
        altrimenti fallback a succeeded+failed come proxy degli scaduti trovati.
        """
        self.relisted += succeeded
        self.failed += failed
        self.cycles += 1
        self.expired_detected += expired_count if expired_count > 0 else (succeeded + failed)

    def is_ready_to_flush(self, current_wait: int) -> bool:
        """
        Determina se è il momento di inviare la notifica.
        Flush se:
        1. C'è stata attività (rilist riusciti o fallimenti)
        2. E si verifica una delle condizioni di flush:
           - Il prossimo wait è lungo (> batch_window), quindi abbiamo finito una 'ondata'
           - Abbiamo raggiunto il numero massimo di cicli
           - È trascorso più di batch_window_seconds dall'ultimo flush (LO-06)
        """
        if self.cycles == 0:
            return False

        # Evita notifiche se non è successo nulla (nessun rilist e nessun fallimento)
        if self.relisted == 0 and self.failed == 0:
            return False

        # Se il bot sta per dormire a lungo, invia subito il report dell'ondata appena conclusa
        if current_wait > self.batch_window_seconds:
            return True

        # Se abbiamo fatto troppi cicli rapidi, flush per dare feedback
        if self.cycles >= self.max_cycles:
            return True

        # LO-06: flush se è già passato batch_window_seconds dall'ultimo report,
        # così l'utente riceve aggiornamenti anche durante ondate lunghe a cicli rapidi.
        if self.last_flush_time is not None:
            elapsed = (datetime.now() - self.last_flush_time).total_seconds()
            if elapsed >= self.batch_window_seconds:
                return True

        return False

    def flush(
        self, app_config, page, logger, scan: ListingScanResult | None = None, last_relist_error: str | None = None
    ):
        """Invia il report aggregato a Telegram e resetta i contatori."""
        if not app_config.notifications.telegram_token:
            return

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            screenshot_path = tmp.name

        try:
            # Report the actual accumulated count since last flush, not capped to current scan
            rilistati = self.relisted
            totale_oggetti = scan.total_count if scan else 0

            # Skip screenshot if on EA sign-in page to avoid credential exposure
            if page and "signin.ea.com" in page.url.lower():
                logger.warning("Skip screenshot: pagina di login (sicurezza credenziali)")
                page = None

            if page:
                page.screenshot(path=screenshot_path)
            error_msg = f" ⚠️ Error: {last_relist_error}" if last_relist_error else ""

            msg = (
                f"🔔 Report Aggregato\n"
                f"-------------------\n"
                f"📦 Cicli: {self.cycles}\n"
                f"📋 Totale oggetti: {totale_oggetti}\n"
                f"⏰ Scaduti rilevati: {self.expired_detected}\n"
                f"🚀 Relistati: {rilistati}\n"
                f"❌ Falliti: {self.failed}{error_msg}\n"
                f"🕒 Modalità: ⚽ Relist Ibrido"
            )

            send_telegram_photo(app_config.notifications, screenshot_path, msg)
            logger.info(f"Notifica batch inviata: {self.relisted} rilistati, {self.failed} falliti.")

        except Exception as e:
            logger.error(f"Errore invio notifica batch: {e}")
        finally:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            self.reset()

    def reset(self):
        """Resetta i contatori del batch."""
        self.relisted = 0
        self.failed = 0
        self.cycles = 0
        self.expired_detected = 0
        self.last_flush_time = datetime.now()

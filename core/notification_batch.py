import logging
from datetime import datetime
from typing import Optional
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
        self.last_flush_time: Optional[datetime] = None

    def accumulate(self, scan: ListingScanResult, succeeded: int, failed: int):
        """Aggiunge i risultati di un ciclo all'accumulatore."""
        self.relisted += succeeded
        self.failed += failed
        self.cycles += 1
        self.expired_detected += scan.expired_count

    def is_ready_to_flush(self, current_wait: int) -> bool:
        """
        Determina se è il momento di inviare la notifica.
        Flush se:
        1. C'è stata attività (rilist riusciti o fallimenti)
        2. E si verifica una delle condizioni di flush:
           - Il prossimo wait è lungo (> batch_window), quindi abbiamo finito una 'ondata'
           - Abbiamo raggiunto il numero massimo di cicli
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
            
        return False

    def flush(self, app_config, page, logger, scan: Optional[ListingScanResult] = None, last_relist_error: Optional[str] = None):
        """Invia il report aggregato a Telegram e resetta i contatori."""
        if not app_config.notifications.telegram_token:
            return

        screenshot_path = "relist_report.png"
        try:
            totale_oggetti = scan.total_count if scan else 0
            
            # Rilistati non può superare il totale oggetti per coerenza logica
            rilistati = min(self.relisted, totale_oggetti) if totale_oggetti else self.relisted
            
            page.screenshot(path=screenshot_path)
            error_msg = f" ⚠️ Error: {last_relist_error}" if last_relist_error else ""
            
            msg = (
                f"🔔 Report Aggregato\n"
                f"-------------------\n"
                f"📦 Cicli: {self.cycles}\n"
                f"📋 Totale oggetti: {totale_oggetti}\n"
                f"🚀 Relistati: {rilistati}\n"
                f"❌ Falliti: {self.failed}{error_msg}\n"
                f"🕒 Modalità: ⚽ Drift Ibrido"
            )
            
            send_telegram_photo(app_config.notifications, screenshot_path, msg)
            logger.info(f"Notifica batch inviata: {rilistati} rilistati, {self.failed} falliti.")
            
        except Exception as e:
            logger.error(f"Errore invio notifica batch: {e}")
        finally:
            import os
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

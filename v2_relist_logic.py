import time
import logging
from datetime import datetime, timedelta

# Mock/Reference logic for integration into main.py
# Questa è la struttura che andrà a sostituire il blocco 'if scan_result.is_empty' in main.py

def implementazione_nuova_logica(page, detector, executor, app_config, cycle, status_console, make_status_table, relist_expired_listings):
    label = f"Ciclo {cycle}"
    logger = logging.getLogger("fifa")
    
    # 1. PASSATA 1 (Minuto :00)
    # Il bot è già arrivato sulla pagina grazie alla pre-navigazione
    logger.info(f"--- [PASSATA 1] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")
    scan_p1 = detector.scan_listings()
    
    succeeded_p1 = 0
    failed_p1 = 0
    
    if scan_p1.expired_count > 0:
        logger.info(f"Pass 1: Trovati {scan_p1.expired_count} scaduti. Rilisto...")
        if executor.relist_mode == "all":
            batch = executor.relist_all(count=scan_p1.expired_count)
            succeeded_p1 = batch.succeeded
            failed_p1 = batch.total - batch.succeeded
        else:
            expired = [l for l in scan_p1.listings if l.needs_relist]
            succeeded_p1, failed_p1 = relist_expired_listings(executor, expired)
        
        logger.info(f"Pass 1 completato: {succeeded_p1} rilistati.")
    else:
        logger.info("Pass 1: Nessun oggetto scaduto trovato.")

    # 2. ATTESA DI SICUREZZA (Fino al secondo :40)
    sync_minute = app_config.listing_defaults.sync_minute_offset
    succeeded_p2 = 0
    failed_p2 = 0
    
    if sync_minute is not None:
        now = datetime.now()
        if now.minute == sync_minute:
            if now.second < 40:
                wait_seconds = 40 - now.second
                logger.info(f"Pausa silenziosa di {wait_seconds}s fino al secondo :40...")
                time.sleep(wait_seconds)

            # Pass 2 always executes if we're in the sync minute
            logger.info(f"--- [PASSATA 2] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")

            # Refresh della pagina (necessario per EA per aggiornare lo stato Unsold)
            try:
                logger.info("Eseguo refresh rapido della UI...")
                transfers_btn = page.get_by_role("button", name="Transfers")
                if not transfers_btn.count():
                    transfers_btn = page.get_by_role("button", name="Trasferimenti")

                if transfers_btn.count():
                    transfers_btn.first.click()
                    page.wait_for_timeout(1500)

                    # Clicca sulla mattonella Transfer List
                    transfer_list_area = page.get_by_role("heading", name="Transfer List")
                    if transfer_list_area.count():
                        transfer_list_area.first.click()
                        page.wait_for_timeout(2000)

                # Seconda scansione
                scan_p2 = detector.scan_listings()
                if scan_p2.expired_count > 0:
                    logger.info(f"Pass 2: Trovati {scan_p2.expired_count} ritardatari. Rilisto...")
                    if executor.relist_mode == "all":
                        batch_p2 = executor.relist_all(count=scan_p2.expired_count)
                        succeeded_p2 = batch_p2.succeeded
                        failed_p2 = batch_p2.total - batch_p2.succeeded
                    else:
                        expired_p2 = [l for l in scan_p2.listings if l.needs_relist]
                        succeeded_p2, failed_p2 = relist_expired_listings(executor, expired_p2)
                    logger.info(f"Pass 2 completato: {succeeded_p2} rilistati.")
                else:
                    logger.info("Pass 2: Nessun ritardatario trovato.")

            except Exception as e:
                logger.error(f"Errore durante il refresh del Pass 2: {e}")
        else:
            logger.info(f"Pass 2 saltato: minuto corrente {now.minute} != sync_minute {sync_minute}.")
    else:
        logger.warning("Pass 2 saltato: sync_minute_offset non configurato.")

    # 4. NOTIFICA FINALE UNIFICATA
    total_succeeded = succeeded_p1 + succeeded_p2
    total_failed = failed_p1 + failed_p2
    
    if total_succeeded > 0 or total_failed > 0:
        logger.info(f"Ciclo completato. Totale: {total_succeeded} successi, {total_failed} fallimenti.")
        
        if app_config.notifications.telegram_token:
            from notifier import send_telegram_photo
            import os
            screenshot_path = "relist_report.png"
            try:
                page.screenshot(path=screenshot_path)
                msg = (
                    f"✅ {label} completato!\n"
                    f"📦 Pass 1 (:00): {succeeded_p1}\n"
                    f"📦 Pass 2 (:40): {succeeded_p2}\n"
                    f"-------------------\n"
                    f"🚀 Totale Rilistati: {total_succeeded}\n"
                    f"🕒 Prossimo: minuto {sync_minute}"
                )
                send_telegram_photo(app_config.notifications, screenshot_path, msg)
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
            except Exception as e:
                logger.error(f"Errore invio notifica: {e}")

    # 5. CALCOLO ATTESA PER IL PROSSIMO GIRO (1 ORA DOPO)
    now = datetime.now()
    if sync_minute is not None:
        # Calcoliamo il minuto target dell'ora successiva
        wait_minutes = (sync_minute - now.minute) % 60
        if wait_minutes <= 0:
            wait_minutes += 60
        
        # Sottraiamo 60 secondi per gestire la pre-navigazione
        next_wait = int(wait_minutes * 60 - now.second) - 60
        if next_wait < 60:
            next_wait = 60
            
        logger.info(f"Fine ciclo. In attesa per {next_wait}s fino al prossimo minuto {sync_minute}.")
        return next_wait
    
    return 3600 # Default fallback

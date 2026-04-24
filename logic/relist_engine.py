from __future__ import annotations
from datetime import datetime
import logging
import random
from typing import Optional, Tuple
from browser.auth import AuthManager
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
from browser.relist import RelistExecutor
from models.listing import ListingState, ListingScanResult
from bot_state import RebootRequestError
from logic.golden_hour import (
    is_in_golden_window,
    is_in_golden_period,
    is_in_hold_window,
    get_next_golden_hour,
    is_close_to_golden,
    get_min_active_seconds
)

logger = logging.getLogger(__name__)
action_logger = logging.getLogger("actions")

class ConsoleSessionError(Exception):
    """Eccezione sollevata quando è attiva una sessione console (rischio ban)."""
    pass

class RelistEngine:
    """
    Orchestra la logica di business del mercato trasferimenti:
    - Scansione dei listing
    - Gestione Golden Hours e Hold Window
    - Esecuzione del rilist con doppia verifica post-azione
    - Calcolo del wait successivo
    """
    def __init__(
        self, 
        page, 
        config, 
        navigator: TransferMarketNavigator, 
        detector: ListingDetector, 
        executor: RelistExecutor,
        auth: AuthManager,
        bot_state
    ):
        self.page = page
        self.config = config
        self.navigator = navigator
        self.detector = detector
        self.executor = executor
        self.auth = auth
        self.bot_state = bot_state

    def process_cycle(self, cycle_num: int, session_keeper) -> Tuple[int, int, int]:
        """
        Esegue un singolo ciclo di gestione rilist.
        Ritorna (succeeded, failed, next_wait).
        """
        # 0. Ban Prevention Hard-Lock
        if self.auth.is_console_session_active(self.page):
            fifa_logger = logging.getLogger("fifa")
            fifa_logger.error("Console session detected - aborting relist to prevent ban")
            
            # Update bot state and notify
            self.bot_state.set_console_session_active(True)
            from notifier import send_telegram_emergency_alert
            send_telegram_emergency_alert(self.config.notifications, "Console session detected! Aborting all relist actions to prevent ban risk.")
            
            raise ConsoleSessionError("Console session detected - aborting relist to prevent ban")

        # 1. Pre-Nav Guard: al minuto :08 NON navigare — aspetta :09:00 senza toccare il browser.
        #    La navigazione avviene SOLO al :09, così il relist scatta esattamente alle :10.
        now_pre = datetime.now()
        if is_in_golden_period(now_pre) and not is_in_golden_window(now_pre):
            next_golden_pre = get_next_golden_hour(now_pre)
            if next_golden_pre and is_close_to_golden(now_pre) and now_pre.minute == 8:
                pre_nav_target = next_golden_pre.replace(minute=9, second=0, microsecond=0)
                wait_secs = max(1, int((pre_nav_target - now_pre).total_seconds()))
                logger.info(f"[Golden] Minuto :08 — attendo pre-nav slot :09:00 (tra {wait_secs}s). Non navigo ancora.")
                if self.bot_state.wait_interruptible(wait_secs):
                    raise RebootRequestError("Reboot richiesto")

        # 2. Navigazione (avviene normalmente, o al minuto :09 durante golden period)
        if not self._navigate_with_retry():
            return 0, 0, 60

        # 3. Golden Sync: dopo la pre-nav al :09, attesa precisa fino alle :10:00
        now = datetime.now()
        next_golden = get_next_golden_hour(now)
        if next_golden and is_in_golden_period(now) and now < next_golden:
            if is_in_golden_window(now) and now.minute == 9:
                wait_secs = (next_golden - now).total_seconds()
                logger.info(f"[Golden] Pre-nav ✅ Transfer List pronta. Attesa precisa: {int(wait_secs)}s per le {next_golden.strftime('%H:%M:%S')}.")
                if self.bot_state.wait_interruptible(wait_secs):
                    raise RebootRequestError("Reboot richiesto")
            elif is_in_golden_window(now):
                logger.info(f"[Golden] Già nella finestra golden (:10-:11), procedo.")

        fifa_logger = logging.getLogger("fifa")
        fifa_logger.info(f"--- [SCANSIONE] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")
        scan = self.detector.scan_listings()

        # 4. Heuristic Relist Manuale
        now_scan = datetime.now()
        if (scan.active_count > 0 and scan.expired_count == 0 and is_in_golden_window(now_scan)):
            seconds_since_bot = self.bot_state.get_seconds_since_last_relist_by_bot()
            if seconds_since_bot is None or seconds_since_bot >= 180:
                # Verifica timer coerenti
                active_times = [l.time_remaining_seconds for l in scan.listings if l.state == ListingState.ACTIVE and l.time_remaining_seconds]
                if active_times:
                    min_t, max_t = min(active_times), max(active_times)
                    if ((3400 <= min_t <= 3600) or (10600 <= min_t <= 10800) or (21400 <= min_t <= 21600)) and (max_t - min_t) <= 90:
                        fifa_logger.info(f"[⚠️ RELIST MANUALE RILEVATO] Bot si ritira. Prossimo check tra {min_t - 20}s.")
                        return 0, 0, max(min_t - 20, 60)

        # 5. Decisione Relist
        if scan.expired_count > 0:
            now_relist = datetime.now()
            in_hold = is_in_hold_window(now_relist)
            force_relist = self.bot_state.consume_force_relist()

            # Regola Ferrea: Minuto :09 posticipa a :10
            if is_in_golden_window(now_relist) and now_relist.minute == 9:
                seconds_to_10 = 60 - now_relist.second
                fifa_logger.info(f"[Golden] Minuto 09, posticipo a :10:00 ({seconds_to_10}s).")
                return 0, 0, seconds_to_10

            if in_hold and not force_relist:
                next_g = get_next_golden_hour(datetime.now())
                if next_g:
                    fifa_logger.info(f"[HOLD] {scan.expired_count} scaduti in HOLD. Prossima golden: {next_g.strftime('%H:%M')}.")
                    return 0, 0, self._compute_next_wait(scan)
                # No more goldens -> override hold
                in_hold = False

            # RELIST NORMALE / FORCE / GOLDEN WINDOW
            if force_relist:
                logger.info("[Telegram] Force relist — bypass hold window")
            
            fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti. Rilisto...")
            
            succeeded, failed = self._execute_relist_with_verification(scan)
            
            # 6. Safety Double Check (Golden Window): se 0 scaduti, verifica ancora e marca come completato.
            now_post = datetime.now()
            if is_in_golden_window(now_post) and (succeeded > 0 or scan.expired_count > 0):
                self.page.wait_for_timeout(7000) # Attesa 7s per allineamento server EA
                safety_scan = self.detector.scan_listings()
                if safety_scan.expired_count == 0 and safety_scan.processing_count == 0:
                    fifa_logger.info(f"[Safety Check] ✅ Conferma 0 scaduti. Golden Hour {now_post.hour}:10 completata con successo.")
                    self.bot_state.mark_golden_completed(now_post.hour)
                else:
                    fifa_logger.warning(f"[Safety Check] ⚠️ Trovati ancora {safety_scan.expired_count} scaduti o {safety_scan.processing_count} in processing. Non marco come completato.")

            # Golden Retry for Processing items
            if is_in_golden_window(datetime.now()):
                retry_s, retry_f, reboot = self._golden_retry_loop(succeeded, failed, scan.processing_count)
                if reboot:
                    raise RebootRequestError("Reboot richiesto dall'utente via Telegram")
                succeeded += retry_s
                failed += retry_f

            return succeeded, failed, self._compute_next_wait(scan)
        
        # Nessun scaduto
        now_final = datetime.now()
        if not is_in_golden_period(now_final):
            # Controllo allineamento scadenze imminenti: 
            # Se ci sono oggetti ACTIVE che scadono entro 30s, non dormire un'ora.
            imminent = [l for l in scan.listings if l.state == ListingState.ACTIVE and l.time_remaining_seconds is not None and l.time_remaining_seconds <= 30]
            if imminent:
                fifa_logger.info(f"Trovati {len(imminent)} oggetti in scadenza imminente (<=30s). Allineamento wait breve.")
                return 0, 0, 20

        return 0, 0, self._compute_next_wait(scan)

    def _execute_relist_with_verification(self, scan: ListingScanResult) -> Tuple[int, int]:
        """Esegue il rilist e verifica i risultati con due round."""
        fifa_logger = logging.getLogger("fifa")
        if self.executor.relist_mode == "all":
            batch = self.executor.relist_all(count=scan.expired_count)
            if batch.relist_error:
                fifa_logger.error(f"ERRORE RELIST: {batch.relist_error}")
                self._save_error_screenshot()
                if self._handle_session_recovery():
                    raise RebootRequestError("Session recovery richiesto")
                return 0, scan.expired_count
            
            self.page.wait_for_timeout(3000)
            post_scan = self.detector.scan_listings()
            
            first_succeeded = max(scan.expired_count - post_scan.expired_count, 0)
            truly_expired = max(post_scan.expired_count - post_scan.processing_count, 0)
            
            if truly_expired > 0:
                fifa_logger.info(f"[Verifica 2°] Ancora {truly_expired} scaduti. Secondo tentativo...")
                second_batch = self.executor.relist_all(count=post_scan.expired_count)
                if second_batch.relist_error:
                    return first_succeeded, truly_expired
                
                self.page.wait_for_timeout(3000)
                final_scan = self.detector.scan_listings()
                second_succeeded = max(post_scan.expired_count - final_scan.expired_count, 0)
                
                # Update stats IMMEDIATELY after success
                self.bot_state.update_stats(relisted=first_succeeded + second_succeeded, failed=max(final_scan.expired_count - final_scan.processing_count, 0))
                
                return first_succeeded + second_succeeded, max(final_scan.expired_count - final_scan.processing_count, 0)
            
            # Update stats IMMEDIATELY after success
            self.bot_state.update_stats(relisted=first_succeeded, failed=0)
            return first_succeeded, 0
        else:
            expired = [l for l in scan.listings if l.needs_relist]
            succeeded = 0
            failed = 0
            for l in expired:
                res = self.executor.relist_single(l)
                if res.success:
                    succeeded += 1
                    action_logger.info("Rilist completato", extra={"action": "relist", "player_name": res.player_name, "success": True})
                else:
                    failed += 1
                    action_logger.warning("Rilist fallito", extra={"action": "relist", "player_name": res.player_name, "success": False, "error": res.error})
            
            # Update stats IMMEDIATELY after loop
            self.bot_state.update_stats(relisted=succeeded, failed=failed)
            return succeeded, failed

    def _golden_retry_loop(self, initial_s, initial_f, processing_count) -> Tuple[int, int, bool]:
        """Retry loop per item in Processing durante Golden window."""
        fifa_logger = logging.getLogger("fifa")
        retry_s, retry_f = 0, 0
        
        if initial_f == 0 and processing_count == 0:
            return 0, 0, False

        while is_in_golden_window(datetime.now()):
            wait_secs = random.uniform(5, 10)
            if self.bot_state.wait_interruptible(wait_secs):
                return retry_s, retry_f, True
            
            if not self._navigate_with_retry():
                break
                
            scan = self.detector.scan_listings()
            if scan.expired_count == 0:
                break
                
            fifa_logger.info(f"[Golden Retry] Trovati {scan.expired_count} item. Rilisto...")
            s, f = self._execute_relist_with_verification(scan)
            retry_s += s
            retry_f += f
            
        return retry_s, retry_f, False

    def _compute_next_wait(self, scan: ListingScanResult) -> int:
        """Calcola il wait ottimale."""
        now = datetime.now()
        
        # Se siamo in Golden Window e abbiamo già completato con successo l'ora corrente,
        # aspettiamo direttamente il prossimo pre-nav (minuto :09 dell'ora successiva)
        # o la fine del golden period (:15) per evitare scansioni a vuoto.
        if is_in_golden_window(now) and self.bot_state.is_golden_completed(now.hour):
            ng = get_next_golden_hour(now)
            # Se la prossima golden è un'ora diversa, puntiamo al suo pre-nav
            if ng and ng.hour > now.hour:
                pre_nav = ng.replace(minute=9, second=0, microsecond=0)
                wait_rest = int((pre_nav - now).total_seconds())
                if wait_rest > 0:
                    logger.info(f"[Golden Success] Ora {now.hour}:10 completata. Salto riposo :15 e punto al pre-nav delle {pre_nav.strftime('%H:%M:%S')} ({wait_rest}s).")
                    return wait_rest
            
            # Altrimenti (ultima golden o caso limite), riposo standard fino al :15
            target_rest = now.replace(minute=15, second=0, microsecond=0)
            wait_rest = int((target_rest - now).total_seconds())
            if wait_rest > 0:
                logger.info(f"[Golden Success] Ora {now.hour}:10 completata. Riposo fino al termine finestra :15 ({wait_rest}s).")
                return wait_rest

        if is_in_hold_window(now):
            ng = get_next_golden_hour(now)
            if ng:
                pre_nav = ng.replace(minute=9, second=0, microsecond=0)
                secs_to_pre_nav = int((pre_nav - now).total_seconds())
                
                # Se mancano meno di 5 minuti, punta ESATTAMENTE alle :09:00
                if 0 < secs_to_pre_nav <= 300:
                    return secs_to_pre_nav
                
                # Altrimenti aspetta fino al pre-nav meno un buffer di 120s per sicurezza, 
                # ma non meno di 60s per evitare troppi heartbeat
                return max(60, secs_to_pre_nav - 120)
            return 3600 - 20

        if is_in_golden_window(now):
            return 10
            
        processing_count = sum(1 for l in scan.listings if l.state == ListingState.ACTIVE and l.time_remaining in ("Processing...", "Elaborazione..."))
        if processing_count > 0:
            return 30
            
        return self._cap_wait(3600 - 20, now)

    def _cap_wait(self, wait: int, now: datetime) -> int:
        if not is_in_golden_period(now):
            # Reset flag di completamento se siamo fuori dalla fascia golden
            # Questo assicura che per la prossima ora golden (es. dalle 16 alle 17) il flag sia pulito.
            self.bot_state.clear_golden_completed()
            return wait
        ng = get_next_golden_hour(now)
        if not ng:
            return wait
        pre_nav = ng.replace(minute=9, second=0, microsecond=0)
        secs_to_pre_nav = int((pre_nav - now).total_seconds())
        return secs_to_pre_nav if 0 < secs_to_pre_nav < wait else wait

    def _navigate_with_retry(self) -> bool:
        try:
            return self.navigator.go_to_transfer_list()
        except Exception:
            self.page.reload()
            self.page.wait_for_timeout(3000)
            try:
                return self.navigator.go_to_transfer_list()
            except Exception:
                return False

    def _handle_session_recovery(self) -> bool:
        if self.executor.check_session_valid():
            return False
        self.page.reload()
        self.page.wait_for_timeout(3000)
        if self.executor.check_session_valid():
            return False
        self.auth.delete_saved_session()
        self.page.goto("https://www.ea.com/fifa/ultimate-team/web-app/")
        self.page.wait_for_timeout(3000)
        return True

    def _save_error_screenshot(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"relist_error_{ts}.png"
        try:
            self.page.screenshot(path=path)
        except Exception:
            pass

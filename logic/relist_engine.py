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

    def process_cycle(self, cycle_num: int, session_keeper) -> Tuple[int, int, int, ListingScanResult]:
        """
        Esegue un singolo ciclo di gestione rilist.
        Ritorna (succeeded, failed, next_wait, scan_result).
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
            return 0, 0, 60, ListingScanResult.empty()

        # 3. Golden Sync: se siamo a :09, il bot è GIÀ sulla Transfer List.
        #    NON scansionare adesso — gli item non sono ancora scaduti.
        #    Aspetta fino a :10:00 e poi scansiona con dati freschi.
        fifa_logger = logging.getLogger("fifa")
        now = datetime.now()
        next_golden = get_next_golden_hour(now)
        if next_golden and is_in_golden_period(now) and now < next_golden:
            if is_in_golden_window(now) and now.minute == 9:
                wait_secs = (next_golden - now).total_seconds()
                logger.info(
                    f"[Golden] In posizione sulla Transfer List ✅ "
                    f"Attendo :10:00 ({int(wait_secs)}s) per scansione + relist."
                )
                if self.bot_state.wait_interruptible(wait_secs):
                    raise RebootRequestError("Reboot richiesto")

        # 4. Scansione — a :10 durante golden (item appena scaduti), subito altrimenti.
        #    Il bot è già sulla Transfer List: scan diretta, ZERO navigazione.
        fifa_logger.info(f"--- [SCANSIONE] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")
        scan = self.detector.scan_listings()

        # 5. Heuristic Relist Manuale
        now_scan = datetime.now()
        if (scan.active_count > 0 and scan.expired_count == 0 and is_in_golden_window(now_scan)):
            seconds_since_bot = self.bot_state.get_seconds_since_last_relist_by_bot()
            if seconds_since_bot is None or seconds_since_bot >= 180:
                active_times = [l.time_remaining_seconds for l in scan.listings if l.state == ListingState.ACTIVE and l.time_remaining_seconds]
                if active_times:
                    min_t, max_t = min(active_times), max(active_times)
                    if ((3400 <= min_t <= 3600) or (10600 <= min_t <= 10800) or (21400 <= min_t <= 21600)) and (max_t - min_t) <= 90:
                        fifa_logger.info(f"[⚠️ RELIST MANUALE RILEVATO] Bot si ritira. Prossimo check tra {min_t - 20}s.")
                        return 0, 0, max(min_t - 20, 60), scan

        # 6. Decisione Relist
        if scan.expired_count > 0:
            now_relist = datetime.now()
            in_hold = is_in_hold_window(now_relist)
            force_relist = self.bot_state.consume_force_relist()

            if in_hold and not force_relist:
                next_g = get_next_golden_hour(datetime.now())
                if next_g:
                    fifa_logger.info(f"[HOLD] {scan.expired_count} scaduti in HOLD. Prossima golden: {next_g.strftime('%H:%M')}.")
                    return 0, 0, 60, scan
                # No more goldens -> override hold
                in_hold = False

            # RELIST NORMALE / FORCE / GOLDEN WINDOW
            if force_relist:
                logger.info("[Telegram] Force relist — bypass hold window")

            # Se TUTTI gli expired sono in realtà PROCESSING, il bottone Re-list All
            # non sarà visibile su EA. Saltiamo il tentativo inutile e lasciamo che
            # il golden_retry_loop aspetti la transizione Processing → Expired.
            truly_expired = scan.expired_count - scan.processing_count
            if truly_expired <= 0 and scan.processing_count > 0 and is_in_golden_window(now_relist):
                fifa_logger.info(
                    f"[Golden] {scan.processing_count} item in Processing (non ancora Expired). "
                    f"Attendo transizione nel retry loop..."
                )
                succeeded, failed = 0, 0
            else:
                fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti. Rilisto...")
                succeeded, failed = self._execute_relist_with_verification(scan)
            
            # Golden Retry for Processing items
            if is_in_golden_window(datetime.now()):
                retry_s, retry_f, reboot = self._golden_retry_loop(succeeded, failed, scan.processing_count)
                if reboot:
                    raise RebootRequestError("Reboot richiesto dall'utente via Telegram")
                succeeded += retry_s
                failed += retry_f

            # Dopo il relist, riscansiona per avere dati freschi per _compute_next_wait
            post_relist_scan = self.detector.scan_listings()
            return succeeded, failed, self._compute_next_wait(post_relist_scan), post_relist_scan
        
        # Nessun scaduto
        return 0, 0, self._compute_next_wait(scan), scan

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
        """Retry loop per item in Processing durante Golden window.
        
        Il bot è GIÀ sulla Transfer List — scan diretta senza navigazione.
        Attesa 5-10s tra i tentativi per dare a EA tempo di transitare.
        """
        fifa_logger = logging.getLogger("fifa")
        retry_s, retry_f = 0, 0
        
        if initial_f == 0 and processing_count == 0:
            return 0, 0, False

        max_retries = 6
        attempt = 0
        while is_in_golden_window(datetime.now()) and attempt < max_retries:
            attempt += 1
            wait_secs = random.uniform(5, 10)
            fifa_logger.info(f"[Golden Retry] Attesa {wait_secs:.0f}s (tentativo {attempt}/{max_retries})...")
            if self.bot_state.wait_interruptible(wait_secs):
                return retry_s, retry_f, True
            
            # Scan diretta — siamo già sulla Transfer List, ZERO navigazione
            scan = self.detector.scan_listings()
            if scan.expired_count == 0:
                fifa_logger.info(f"[Golden Retry] Nessun expired rimasto. Fine.")
                break

            # Se sono tutti ancora Processing, aspetta ancora
            truly_expired = scan.expired_count - scan.processing_count
            if truly_expired <= 0 and scan.processing_count > 0:
                fifa_logger.info(f"[Golden Retry] Ancora {scan.processing_count} in Processing, attendiamo...")
                continue
                
            fifa_logger.info(f"[Golden Retry] Trovati {scan.expired_count} item. Rilisto...")
            s, f = self._execute_relist_with_verification(scan)
            retry_s += s
            retry_f += f
            
            if f == 0:
                break
            
        return retry_s, retry_f, False

    def _compute_next_wait(self, scan: ListingScanResult) -> int:
        """Calcola il wait ottimale."""
        now = datetime.now()
        # In golden window, polling rapido SOLO se ci sono ancora item da relistare.
        # Se expired_count == 0 dopo il relist, NON continuare a scansionare ogni 10s:
        # calcola il wait normale verso la prossima golden pre-nav.
        if is_in_golden_window(now) and (scan.expired_count > 0 or scan.processing_count > 0):
            return 10
        
        min_active = get_min_active_seconds(scan)
        if min_active:
            wait = max(min_active - 20, 10)
            return self._cap_wait(wait, now)
        
        if is_in_hold_window(now):
            ng = get_next_golden_hour(now)
            if ng:
                # Mira al minuto :08 per dare tempo al Pre-Nav Guard di attivarsi.
                # Il Guard aspetterà da :08 a :09, poi il bot naviga a :09.
                wake_target = ng.replace(minute=8, second=0, microsecond=0)
                secs_to_wake = int((wake_target - now).total_seconds())
                return max(30, secs_to_wake)
            return 3600 - 20
            
        if scan.processing_count > 0:
            return 30
            
        return self._cap_wait(3600 - 20, now)

    def _cap_wait(self, wait: int, now: datetime) -> int:
        """Limita il wait per non superare il prossimo slot :08 durante il golden period."""
        if not is_in_golden_period(now):
            return wait
        ng = get_next_golden_hour(now)
        if not ng:
            return wait
        # Mira a :08:00 per dare al Pre-Nav Guard tempo di gestire :08→:09→nav→:10
        wake_target = ng.replace(minute=8, second=0, microsecond=0)
        secs_to_wake = int((wake_target - now).total_seconds())
        return secs_to_wake if 0 < secs_to_wake < wait else wait

    def _navigate_with_retry(self, force: bool = False) -> bool:
        # Quick check: siamo già nella Transfer List? (solo se non force)
        if not force:
            try:
                transfer_selectors = ['.ut-transfer-list-view', '.listFUTItem', '.no-items', '.empty-list', '.no-listings']
                for sel in transfer_selectors:
                    if self.page.locator(sel).count() > 0:
                        logger.debug("Già nella Transfer List → skip navigazione")
                        return True
            except Exception as e:
                logger.debug(f"Quick check Transfer List fallito: {e}")
        
        # Navigazione completa
        try:
            return self.navigator.go_to_transfer_list(fast=force)
        except Exception:
            self.page.reload()
            self.page.wait_for_timeout(3000)
            try:
                return self.navigator.go_to_transfer_list(fast=force)
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

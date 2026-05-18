from __future__ import annotations

import logging
import random
from contextlib import suppress
from datetime import datetime

from bot_state import RebootRequestError
from browser.auth import AuthManager
from browser.detector import ListingDetector
from browser.navigator import TransferMarketNavigator
from browser.relist import RelistExecutor
from logic.golden_hour import (
    GOLDEN_RETRY_MAX_ATTEMPTS,
    GOLDEN_RETRY_MAX_WAIT,
    GOLDEN_RETRY_MIN_WAIT,
    PROCESSING_MAX_ATTEMPTS,
    PROCESSING_MAX_TOTAL_TIME,
    PROCESSING_MAX_WAIT,
    PROCESSING_MIN_WAIT,
    get_min_active_seconds,
    get_next_golden_hour,
    is_close_to_golden,
    is_in_golden_period,
    is_in_golden_window,
    is_in_hold_window,
)
from models.listing import ListingScanResult, ListingState

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
        bot_state,
    ):
        self.page = page
        self.config = config
        self.navigator = navigator
        self.detector = detector
        self.executor = executor
        self.auth = auth
        self.bot_state = bot_state
        self._last_scan_result: ListingScanResult | None = None
        self._fifa_logger = logging.getLogger("fifa")  # LO-01: singleton, non ri-ottenuto ogni metodo
        self._fast_idle_cycles: int = 0  # Contatore per stale page detection

    def process_cycle(
        self,
    ) -> tuple[
        int, int, int, ListingScanResult, datetime | None, int
    ]:  # ME-12: rimossi cycle_num e session_keeper (non utilizzati)
        """
        Esegue un singolo ciclo di gestione rilist.
        Ritorna (succeeded, failed, next_wait, scan_result, deadline, pre_relist_expired_count).

        La deadline è la prossima :08:00 durante il golden period (per il Pre-Nav Guard).
        """
        deadline = None
        self._last_scan_result = None  # Reset per evitare dati stale da cicli precedenti
        # 0. Ban Prevention Hard-Lock
        if self.auth.is_console_session_active(self.page):
            self._fifa_logger.error("Console session detected - aborting relist to prevent ban")

            # Update bot state and notify
            self.bot_state.set_console_session_active(True)

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
            deadline = self._compute_deadline(datetime.now())
            return 0, 0, 60, ListingScanResult.empty(), deadline, 0

        # 3. Golden Sync: se siamo a :09, il bot è GIÀ sulla Transfer List.
        #    NON scansionare adesso — gli item non sono ancora scaduti.
        #    Aspetta fino a :10:00 e poi scansiona con dati freschi.
        now = datetime.now()
        next_golden = get_next_golden_hour(now)
        if (
            next_golden
            and is_in_golden_period(now)
            and is_in_golden_window(now)
            and now.minute == 9
            and now < next_golden
        ):
            wait_secs = (next_golden - now).total_seconds()
            logger.info(
                f"[Golden] In posizione sulla Transfer List ✅ "
                f"Attendo :10:00 ({int(wait_secs)}s) per scansione + relist."
            )
            if self.bot_state.wait_interruptible(wait_secs):
                raise RebootRequestError("Reboot richiesto")

        # 4. Scansione — a :10 durante golden (item appena scaduti), subito altrimenti.
        #    Il bot è già sulla Transfer List: scan diretta, ZERO navigazione.
        self._fifa_logger.info(f"--- [SCANSIONE] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")
        scan = self.detector.scan_listings()
        pre_expired_count = scan.expired_count  # Salva il conteggio pre-relist per il return

        # 5. Heuristic Relist Manuale
        #    Rileva quando l'utente ha effettuato un relist manuale (batch di item listati insieme).
        #    Pattern: tutti gli item attivi hanno tempo_remaining simile (entro 90s) e ricadono in
        #    finestre temporali caratteristiche di relist manuali:
        #      • 3400-3600s  (~57-60 min)  → relist orario
        #      • 10600-10800s (~177-180 min) → relist ogni 3 ore
        #      • 21400-21600s (~357-360 min) → relist ogni 6 ore
        #    Questi range derivano dall'osservazione dei pattern di comportamento utente:
        #    l'utente tende a relistare a intervalli "tondi" (1h, 3h, 6h) per evitare di dimenticare.
        #    La condizione `seconds_since_bot >= 180` evita falsi positivi se il bot ha appena
        #    eseguito un relist automatico (che potrebbe lasciare item con timer simili).
        now_scan = datetime.now()
        if scan.active_count > 0 and scan.expired_count == 0 and is_in_golden_window(now_scan):
            seconds_since_bot = self.bot_state.get_seconds_since_last_relist_by_bot()
            if seconds_since_bot is None or seconds_since_bot >= 180:
                active_times = [
                    listing.time_remaining_seconds
                    for listing in scan.listings
                    if listing.state == ListingState.ACTIVE and listing.time_remaining_seconds
                ]
                if active_times:
                    min_t, max_t = min(active_times), max(active_times)
                    # Il delta <= 90s (1.5 min) garantisce che tutti gli item siano stati listati
                    # nell stesso "burst" manuale, non in sessioni separate.
                    if ((3400 <= min_t <= 3600) or (10600 <= min_t <= 10800) or (21400 <= min_t <= 21600)) and (
                        max_t - min_t
                    ) <= 90:
                        self._fifa_logger.info(
                            f"[⚠️ RELIST MANUALE RILEVATO] Bot si ritira. Prossimo check tra {min_t - 20}s."
                        )
                        deadline = self._compute_deadline(datetime.now())
                        return 0, 0, max(min_t - 20, 60), scan, deadline, pre_expired_count

        # 6. Decisione Relist
        if scan.expired_count > 0:
            self._fast_idle_cycles = 0  # Reset: ci sono expired, la pagina è viva
            now_relist = datetime.now()
            in_hold = is_in_hold_window(now_relist)
            force_relist = self.bot_state.consume_force_relist()

            if in_hold and not force_relist:
                next_g = get_next_golden_hour(now_relist)
                if next_g:
                    # Calcola il wait fino al minuto :08 della prossima golden
                    # così il Pre-Nav Guard si attiva correttamente.
                    # FIX RACE CONDITION: usa lo stesso timestamp per tutti i calcoli
                    wake_target = next_g.replace(minute=8, second=0, microsecond=0)
                    hold_wait = max(30, int((wake_target - now_relist).total_seconds()))
                    self._fifa_logger.info(
                        f"[HOLD] {scan.expired_count} scaduti in HOLD. Prossima golden: {next_g.strftime('%H:%M')}. Attesa: {hold_wait}s."
                    )
                    deadline = self._compute_deadline(now_relist)
                    return 0, 0, hold_wait, scan, deadline, pre_expired_count
                # No more goldens -> override hold
                in_hold = False

            # RELIST NORMALE / FORCE / GOLDEN WINDOW
            if force_relist:
                logger.info("[Telegram] Force relist — bypass hold window")

            # Calcola quanti sono veramente "expired" (non processing)
            truly_expired = max(0, scan.expired_count - scan.processing_count)  # HI-04

            # Caso 1: Solo processing items (truly_expired <= 0)
            # Il bottone "Re-list All" NON è visibile su EA finché gli item sono in
            # stato Processing (limbo EA post-scadenza). Aspettiamo il retry loop.
            if truly_expired <= 0 and scan.processing_count > 0:
                if is_in_golden_window(now_relist):
                    self._fifa_logger.info(
                        f"[Golden] {scan.processing_count} item in Processing (non ancora Expired). "
                        f"Attendo transizione nel retry loop..."
                    )
                else:
                    self._fifa_logger.info(
                        f"[Processing] {scan.processing_count} item in Processing (limbo EA). "
                        f"Il bottone 'Re-list All' non è ancora disponibile. Attesa..."
                    )
                succeeded, failed = 0, 0
            else:
                # Caso 2: Ci sono veri expired item - procedi con il relist
                self._fifa_logger.info(
                    f"Trovati {scan.expired_count} oggetti scaduti ({truly_expired} veri expired). Rilisto..."
                )
                succeeded, failed = self._execute_relist_with_verification(scan)

            # Golden Retry: usa dati POST-relist (freschi) per decidere se partire.
            # self._last_scan_result è aggiornato da _execute_relist_with_verification.
            # Se processing_count == 0 e failed == 0, la guardia interna al loop
            # blocca immediatamente l'esecuzione — nessun wait inutile.
            post_exec_scan = self._last_scan_result or scan
            post_processing = post_exec_scan.processing_count

            if is_in_golden_window(datetime.now()):
                retry_s, retry_f, reboot = self._golden_retry_loop(succeeded, failed, post_processing)
                if reboot:
                    raise RebootRequestError("Reboot richiesto dall'utente via Telegram")
                succeeded += retry_s
                # Il retry recupera item che erano falliti nel relist iniziale.
                # Ogni succeeded del retry compensa un failed originale.
                failed = max(failed - retry_s + retry_f, 0)
            # Processing wait loop - handles processing items outside golden window.
            # Usa self._last_scan_result (post-relist) per catturare sia il Caso 1
            # (solo processing) sia il Caso 2 con residui processing dopo un relist parziale.
            else:
                interim_scan = self._last_scan_result or scan
                if interim_scan.processing_count > 0:
                    self._fifa_logger.info(
                        f"[Processing] {interim_scan.processing_count} item ancora in limbo EA "
                        f"— attendo transizione prima di tornare al ciclo principale..."
                    )
                    proc_s, proc_f = self._processing_wait_loop(interim_scan.processing_count)
                    succeeded += proc_s
                    failed += proc_f

            # Usa l'ultimo risultato disponibile (aggiornato durante la verifica)
            # per calcolare il prossimo wait senza scansionare di nuovo il DOM.
            post_relist_scan = self._last_scan_result or self.detector.scan_listings()
            deadline = self._compute_deadline(datetime.now())
            return succeeded, failed, self._compute_next_wait(post_relist_scan), post_relist_scan, deadline, pre_expired_count

        # Nessun scaduto
        next_wait = self._compute_next_wait(scan)

        # Stale Page Detection: se il bot fa cicli rapidi (≤30s) consecutivi
        # senza trovare mai expired, la pagina è probabilmente congelata
        # (sessione EA scaduta, timer DOM bloccati su valori bassi).
        if next_wait <= 30 and scan.active_count > 0:
            self._fast_idle_cycles += 1
            if self._fast_idle_cycles >= 10:
                self._fifa_logger.warning(
                    f"[Stale Detection] {self._fast_idle_cycles} cicli rapidi senza expired "
                    f"— pagina probabilmente congelata. Forzo reload..."
                )
                self._fast_idle_cycles = 0
                self._last_scan_result = None
                self.page.reload()
                self.page.wait_for_timeout(5000)
                # Riscansioniamo con dati freschi
                scan = self.detector.scan_listings()
                self._last_scan_result = scan
                next_wait = self._compute_next_wait(scan)
        else:
            self._fast_idle_cycles = 0

        deadline = self._compute_deadline(datetime.now())
        return 0, 0, next_wait, scan, deadline, pre_expired_count

    def _execute_relist_with_verification(self, scan: ListingScanResult) -> tuple[int, int]:
        """Esegue il rilist e verifica i risultati con due round."""
        if self.executor.relist_mode == "all":
            batch = self.executor.relist_all(count=scan.expired_count)
            if batch.relist_error:
                self._fifa_logger.error(f"ERRORE RELIST: {batch.relist_error}")
                self._save_error_screenshot()
                if self._handle_session_recovery():
                    raise RebootRequestError("Session recovery richiesto")
                return 0, scan.expired_count

            self.page.wait_for_timeout(3000)
            try:
                post_scan = self.detector.scan_listings()
                self._last_scan_result = post_scan
            except Exception as e:
                logger.error(f"Scan verifica post-relist fallita: {e}")
                return 0, scan.expired_count  # HI-03: fallback conservativo

            first_succeeded = max(scan.expired_count - post_scan.expired_count, 0)
            truly_expired = max(post_scan.expired_count - post_scan.processing_count, 0)  # HI-04

            if truly_expired > 0:
                self._fifa_logger.info(f"[Verifica 2°] Ancora {truly_expired} scaduti. Secondo tentativo...")
                second_batch = self.executor.relist_all(count=post_scan.expired_count)
                if second_batch.relist_error:
                    return first_succeeded, truly_expired

                self.page.wait_for_timeout(3000)
                try:
                    final_scan = self.detector.scan_listings()
                    self._last_scan_result = final_scan
                except Exception as e:
                    logger.error(f"Scan verifica finale post-relist fallita: {e}")
                    return first_succeeded, truly_expired  # HI-03: fallback conservativo

                second_succeeded = max(post_scan.expired_count - final_scan.expired_count, 0)

                # Update stats IMMEDIATELY after success
                self.bot_state.update_stats(
                    relisted=first_succeeded + second_succeeded,
                    failed=max(final_scan.expired_count - final_scan.processing_count, 0),
                )
                action_logger.info(
                    "Rilist batch completato",
                    extra={  # ME-01
                        "action": "relist_batch",
                        "success": True,
                        "relisted": first_succeeded + second_succeeded,
                        "failed": max(final_scan.expired_count - final_scan.processing_count, 0),
                    },
                )
                return first_succeeded + second_succeeded, max(
                    final_scan.expired_count - final_scan.processing_count, 0
                )

            # Update stats IMMEDIATELY after success (truly_expired <= 0)
            self.bot_state.update_stats(relisted=first_succeeded, failed=0)
            action_logger.info(
                "Rilist batch completato",
                extra={  # ME-01
                    "action": "relist_batch",
                    "success": True,
                    "relisted": first_succeeded,
                    "failed": 0,
                },
            )
            return first_succeeded, 0
        else:
            expired = [listing for listing in scan.listings if listing.needs_relist]
            succeeded = 0
            failed = 0
            for listing in expired:
                res = self.executor.relist_single(listing)
                if res.success:
                    succeeded += 1
                    action_logger.info(
                        "Rilist completato", extra={"action": "relist", "player_name": res.player_name, "success": True}
                    )
                else:
                    failed += 1
                    action_logger.warning(
                        "Rilist fallito",
                        extra={
                            "action": "relist",
                            "player_name": res.player_name,
                            "success": False,
                            "error": res.error,
                        },
                    )

            # Update stats IMMEDIATELY after loop
            self.bot_state.update_stats(relisted=succeeded, failed=failed)
            # ME-14: aggiorna _last_scan_result dopo il relist per_listing
            try:
                self._last_scan_result = self.detector.scan_listings()
            except Exception:
                logger.debug("Scan post-relist per_listing fallita (non critico)", exc_info=True)
            return succeeded, failed

    def _golden_retry_loop(self, initial_s, initial_f, processing_count) -> tuple[int, int, bool]:
        """Retry loop per item in Processing durante Golden window.

        Il bot è GIÀ sulla Transfer List — scan diretta senza navigazione.
        Attesa 5-10s tra i tentativi per dare a EA tempo di transitare.
        """
        retry_s, retry_f = 0, 0

        if initial_f == 0 and processing_count == 0:
            return 0, 0, False

        max_retries = GOLDEN_RETRY_MAX_ATTEMPTS
        attempt = 0
        while is_in_golden_window(datetime.now()) and attempt < max_retries:
            attempt += 1
            wait_secs = random.uniform(GOLDEN_RETRY_MIN_WAIT, GOLDEN_RETRY_MAX_WAIT)
            self._fifa_logger.info(f"[Golden Retry] Attesa {wait_secs:.0f}s (tentativo {attempt}/{max_retries})...")
            if self.bot_state.wait_interruptible(wait_secs):
                return retry_s, retry_f, True

            # Scan diretta — siamo già sulla Transfer List, ZERO navigazione
            scan = self.detector.scan_listings()
            self._last_scan_result = scan
            if scan.expired_count == 0:
                self._fifa_logger.info("[Golden Retry] Nessun expired rimasto. Fine.")
                break

            # Se sono tutti ancora Processing, aspetta ancora
            truly_expired = max(0, scan.expired_count - scan.processing_count)  # HI-04
            if truly_expired <= 0 and scan.processing_count > 0:
                self._fifa_logger.info(f"[Golden Retry] Ancora {scan.processing_count} in Processing, attendiamo...")
                continue

            # Guard aggiuntiva per evitare di eseguire il relist quando non ci sono expired reali
            if truly_expired <= 0:
                self._fifa_logger.info("[Golden Retry] Nessun expired reale trovato dopo processing check. Fine.")
                break

            self._fifa_logger.info(f"[Golden Retry] Trovati {scan.expired_count} item. Rilisto...")
            s, f = self._execute_relist_with_verification(scan)
            retry_s += s
            retry_f += f

            # Esci solo se non ci sono né failed né processing residui.
            # Se ci sono ancora processing (limbo EA), il loop continua
            # ad aspettare la loro transizione invece di delegare al ciclo principale.
            post_retry_scan = self._last_scan_result
            remaining_processing = post_retry_scan.processing_count if post_retry_scan else 0
            if f == 0 and remaining_processing == 0:
                self._fifa_logger.info("[Golden Retry] Tutto rilistato, nessun processing residuo. Fine.")
                break

        return retry_s, retry_f, False

    def _processing_wait_loop(self, processing_count: int) -> tuple[int, int]:
        """Wait loop for processing items outside golden window.

        Items in 'Processing' state (EA limbo after expiration) transition
        to 'Expired' automatically. This loop waits with periodic scans
        and relists immediately when items are ready.

        Enhanced with:
        - More attempts (15 instead of 3)
        - Longer wait times (30-60s instead of 15-30s)
        - Total timeout fallback (5 minutes)
        """
        scan = self._last_scan_result  # HI-02: fallback iniziale prima del loop
        max_attempts = PROCESSING_MAX_ATTEMPTS
        attempt = 0
        total_time_elapsed = 0

        while attempt < max_attempts and total_time_elapsed < PROCESSING_MAX_TOTAL_TIME:
            attempt += 1
            self._fifa_logger.info(
                f"[Processing] Attesa {attempt}/{max_attempts} ({total_time_elapsed}s/{PROCESSING_MAX_TOTAL_TIME}s) — "
                f"{scan.processing_count if scan else processing_count} item in limbo EA..."  # ME-04: valore attuale
            )

            # Calculate remaining time to not exceed total timeout
            remaining_timeout = PROCESSING_MAX_TOTAL_TIME - total_time_elapsed
            wait_secs = max(1, min(random.uniform(PROCESSING_MIN_WAIT, PROCESSING_MAX_WAIT), remaining_timeout))

            if self.bot_state.wait_interruptible(int(wait_secs)):
                return 0, 0

            total_time_elapsed += int(wait_secs)

            # Scan to check if items transitioned
            scan = self.detector.scan_listings()
            self._last_scan_result = scan

            new_truly_expired = max(0, scan.expired_count - scan.processing_count)  # HI-04
            if new_truly_expired > 0:
                self._fifa_logger.info(
                    f"[Processing] Transizione completata! {new_truly_expired} item ora Expired dopo {total_time_elapsed}s. "
                    f"Rilisto subito..."
                )
                return self._execute_relist_with_verification(scan)

        # Fallback strategy: if we exhausted all attempts or hit total timeout
        if total_time_elapsed >= PROCESSING_MAX_TOTAL_TIME:
            self._fifa_logger.warning(
                f"[Processing] Timeout massimo raggiunto ({PROCESSING_MAX_TOTAL_TIME}s). "
                f"{scan.processing_count} item rimangono in limbo EA. "
                f"Item verranno processati al prossimo ciclo."
            )
        else:
            self._fifa_logger.warning(
                f"[Processing] Tentativi massimi raggiunti ({max_attempts}). "
                f"{scan.processing_count} item rimangono in limbo EA. "
                f"Item verranno processati al prossimo ciclo."
            )

        return 0, 0

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
            return self._limit_wait_for_pre_nav(wait, now)

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

        return self._limit_wait_for_pre_nav(3600 - 20, now)

    def _limit_wait_for_pre_nav(self, wait: int, now: datetime) -> int:  # LO-09: rinominato da _cap_wait
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

    def _compute_deadline(self, now: datetime) -> datetime | None:
        """Calcola la deadline per il Pre-Nav Guard (prossima :08:00)."""
        if not is_in_golden_period(now):
            return None

        ng = get_next_golden_hour(now)  # Ora restituisce SEMPRE la futura
        if not ng:
            return None

        # ng è sempre futura, quindi deadline è sempre futura
        deadline = ng.replace(minute=8, second=0, microsecond=0)
        return deadline

    # ME-05: selettori CSS per il quick-check Transfer List.
    # Default hardcoded come fallback; override in config["transfer_list_selectors"]
    # per adattarsi ad aggiornamenti della WebApp EA senza modificare il codice.
    _DEFAULT_TRANSFER_SELECTORS = [
        ".ut-transfer-list-view",
        ".listFUTItem",
        ".no-items",
        ".empty-list",
        ".no-listings",
    ]

    def _navigate_with_retry(self, force: bool = False) -> bool:
        # Quick check: siamo già nella Transfer List? (solo se non force)
        if not force:
            try:
                transfer_selectors = self.config.get(
                    "transfer_list_selectors",
                    self._DEFAULT_TRANSFER_SELECTORS,
                )
                for sel in transfer_selectors:
                    if self.page.locator(sel).count() > 0:
                        logger.debug("Già nella Transfer List → skip navigazione")
                        return True
            except Exception as e:
                logger.debug(f"Quick check Transfer List fallito: {e}")

        # Navigazione completa
        try:
            return self.navigator.go_to_transfer_list(fast=force)
        except (RebootRequestError, ConsoleSessionError):
            raise
        except Exception:
            self.page.reload()
            self.page.wait_for_timeout(3000)
            try:
                return self.navigator.go_to_transfer_list(fast=force)
            except (RebootRequestError, ConsoleSessionError):
                raise
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
        # LO-03: URL da config invece di hardcoded
        self.page.goto(self.config.get("fifa_webapp_url", "https://www.ea.com/ea-sports-fc/ultimate-team/web-app/"))
        self.page.wait_for_timeout(3000)
        return True

    def _save_error_screenshot(self):
        from pathlib import Path

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # ME-15: path assoluto configurabile invece di CWD relativo
        screenshot_dir = Path(self.config.get("screenshot_dir", "logs/screenshots"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = screenshot_dir / f"relist_error_{ts}.png"
        with suppress(Exception):
            self.page.screenshot(path=path)

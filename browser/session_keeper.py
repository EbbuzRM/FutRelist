from __future__ import annotations

import logging
import os
import random
import sys
import time
from datetime import datetime

from bot_state import BotState, RebootRequestError
from browser.auth import AuthManager
from browser.controller import BrowserController
from browser.error_handler import ensure_session
from notifier import send_telegram_error_with_screenshot

logger = logging.getLogger(__name__)


class SessionKeeper:
    """
    Gestisce la supervisione della sessione browser:
    - Heartbeat per mantenere la sessione attiva
    - Gestione della modalità Console (deep sleep) e Pausa
    - Attese interruttibili da comandi Telegram
    """

    def __init__(
        self,
        controller: BrowserController,
        auth: AuthManager,
        bot_state: BotState,
        page,
        get_credentials_fn,
        notifications_config,
    ):
        self.controller = controller
        self.auth = auth
        self.bot_state = bot_state
        self.page = page
        self.get_credentials = get_credentials_fn
        self.notifications_config = notifications_config

    def ensure_session(self, timeout_ms: int = 10000) -> None:
        """Verifica e ripristina la sessione se necessaria."""
        ensure_session(
            self.page,
            self.auth,
            self.controller,
            timeout_ms=timeout_ms,
            wait_fn=self.bot_state.wait_interruptible,
        )

    def supervise_state(self, status_console) -> bool:
        """
        Valuta se il bot deve essere in deep sleep o pausa.
        Ritorna True se il bot è in uno stato che richiede l'attesa (console/pause)
        e non ci sono comandi pendenti. Ritorna False se un comando Telegram
        interrompe l'attesa, permettendo al main loop di processarlo.
        """
        if self.bot_state.is_console_mode():
            until = self.bot_state.get_console_mode_until()
            until_str = f" (auto-resume alle {until.strftime('%H:%M')})" if until else ""
            logger.info(f"[Console Mode] 🎮 Deep sleep{until_str} — zero interazione WebApp")
            status_console.print(self._make_status_table("🎮 Console Mode", 0, 0, 0))
            # Se wait_interruptible ritorna False, un comando Telegram è in arrivo:
            # restituisci False per permettere al main loop di processarlo.
            if self.bot_state.wait_interruptible(self._state_wait_seconds(until)):  # si sveglia subito su /reboot
                return True
            return False

        if self.bot_state.is_paused():
            until = self.bot_state.get_pause_until()
            until_str = f" (auto-resume alle {until.strftime('%H:%M')})" if until else ""
            logger.info(f"[Telegram] Bot in pausa{until_str} — skip scanning")
            status_console.print(self._make_status_table(f"⏸️ In Pausa (Telegram){until_str}", 0, 0, 0))
            # Se wait_interruptible ritorna False, un comando Telegram è in arrivo:
            # restituisci False per permettere al main loop di processarlo.
            if self.bot_state.wait_interruptible(
                self._state_wait_seconds(until)
            ):  # si sveglia subito su /resume o /reboot
                return True
            return False

        return False

    def _state_wait_seconds(self, until: datetime | None, default_seconds: int = 300) -> int:
        """Cappa l'attesa alla deadline di auto-resume, se presente."""
        if not until:
            return default_seconds
        remaining = int((until - datetime.now()).total_seconds())
        return max(1, min(default_seconds, remaining))

    def wait_with_heartbeat(
        self,
        wait_seconds: int,
        logger_instance: logging.Logger,
        deadline: datetime | None = None,
        min_heartbeat_delay: int = 150,
        max_heartbeat_delay: int = 300,
    ) -> bool:
        """
        Attesa in chunk con Heartbeat (click 'Transfers') per mantenere la sessione.
        Ritorna True se un reboot è stato richiesto.

        Args:
            deadline: Se specificato, cappa i chunk per svegliarsi entro 5s della deadline.
                     Usato per il Pre-Nav Guard (sveglia entro :08:05).
        """
        start_time = datetime.now()

        while True:
            # ⚠️ datetime.now() all'inizio di ogni iterazione per precisione temporale
            now = datetime.now()

            elapsed = (now - start_time).total_seconds()
            remaining = wait_seconds - elapsed
            if remaining <= 0:
                break

            current_heartbeat_interval = random.randint(min_heartbeat_delay, max_heartbeat_delay)
            chunk = min(float(current_heartbeat_interval), remaining)

            # ⚠️ DEADLINE CHECK: se c'è una deadline (es. prossima :08:00),
            # cappa il chunk per svegliarsi in tempo
            if deadline:
                secs_to_deadline = (deadline - now).total_seconds()

                # ⚠️ CHECK IMMEDIATO: se deadline già raggiunta, esci subito
                if secs_to_deadline <= 0:
                    logger_instance.info(
                        f"Deadline {deadline.strftime('%H:%M:%S')} già raggiunta, esco subito dal wait per Pre-Nav Guard"
                    )
                    break

                if secs_to_deadline > 0 and secs_to_deadline < chunk:
                    chunk = max(1, secs_to_deadline)  # Sveglia entro la deadline (1s safety)
                    logger_instance.debug(
                        f"Deadline {deadline.strftime('%H:%M:%S')} tra {secs_to_deadline:.1f}s, cappo chunk a {chunk}s"
                    )

            if self.bot_state.wait_interruptible(chunk):
                return True  # Reboot richiesto

            # ⚠️ CONTROLLO DEADLINE: dopo il chunk sleep, controlla se siamo alla deadline
            if deadline:
                if datetime.now() >= deadline:
                    logger_instance.info(
                        f"Deadline {deadline.strftime('%H:%M:%S')} raggiunta, esco dal wait per Pre-Nav Guard"
                    )
                    break  # Esce dal while, ritorna al chiamante

            if self.bot_state.has_commands():
                return False  # Interrotto per comandi

            elapsed_after_wait = (datetime.now() - start_time).total_seconds()
            if (
                wait_seconds - elapsed_after_wait > 0
                and not self.bot_state.is_paused()
                and not self.bot_state.is_console_mode()
            ):
                self._execute_heartbeat()

        return False

    def _execute_heartbeat(self) -> None:
        """Esegue l'azione di heartbeat cliccando 'Transfers' nella sidebar.

        Cliccando 'Transfers' si forza una richiesta al server EA, garantendo
        un heartbeat reale anche quando non ci sono oggetti venduti.
        Dopo il click, gestisce eventuali popup/modali di sessione scaduta.
        """
        try:
            # 1. Chiude eventuali popup invisibili che intercettano i pointer events
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)

            # 2. Cerca il pulsante Transfers nella sidebar (usando CSS robusto + fallback testuali)
            transfers_btn = self.page.locator("button.ut-tab-bar-item.icon-transfer")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name="Transfers")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name=" Transfers")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name="Trasferimenti")
            if not transfers_btn.count():
                transfers_btn = self.page.get_by_role("button", name=" Trasferimenti")

            if transfers_btn.count():
                # 3. Clicca con force=True per bypassare "intercepts pointer events"
                transfers_btn.first.click(timeout=3000, force=True)
                logger.debug("Heartbeat: click su 'Transfers' eseguito")
                self.page.wait_for_timeout(2000)

                # Gestisci eventuali popup/modali EA
                self._handle_post_heartbeat_modals()
            else:
                logger.debug("Heartbeat: pulsante 'Transfers' non visibile, skip")

            # Check sessione dopo heartbeat
            if self.auth.is_console_session_active(self.page):
                logger.warning("Heartbeat ha rilevato la console in uso!")
                self.bot_state.set_console_session_active(True)
                # Attiva console_mode con auto-resume 30 min
                if not self.bot_state.is_console_mode():
                    logger.warning("Heartbeat: attivazione auto Console Mode (30 min) per evitare spam.")
                    self.bot_state.set_console_mode(True, hours=0.5)
                return  # ME-07: ESCI SUBITO dopo aver attivato console mode

            if not self.auth.is_logged_in(self.page, timeout_ms=3000):
                logger.warning("Heartbeat ha rilevato sessione scaduta.")

                try:
                    logger.info("Tentativo di recupero sessione...")
                    self.ensure_session(timeout_ms=10000)

                    if self.auth.is_logged_in(self.page, timeout_ms=3000):
                        logger.info("Recupero sessione riuscito!")
                    else:
                        raise Exception("Recupero sessione fallito - utente non ancora autenticato")

                except Exception as recovery_error:
                    logger.error(f"Recupero sessione fallito: {recovery_error}")

                    send_telegram_error_with_screenshot(
                        self.notifications_config,
                        f"❌ Recupero sessione fallito: {recovery_error}. Riavvio il bot...",
                        page=self.page,
                    )

                    # HI-06: Solleva RebootRequestError per riavviare il bot
                    raise RebootRequestError(f"Impossibile recuperare la sessione: {recovery_error}")

        except RebootRequestError:
            raise  # HI-06: Propaga SEMPRE RebootRequestError
        except Exception as e:
            # FIX: logging più esplicito per non nascondere errori reali
            logger.error(f"Errore heartbeat non gestito: {type(e).__name__}: {e}")
            logger.debug("Errore heartbeat stacktrace: ", exc_info=True)

    def _handle_post_heartbeat_modals(self) -> None:
        """Gestisce popup/modali EA che possono apparire dopo il click Transfers.

        Delega al AuthManager la gestione dei modali di disconnessione (ME-08).
        """
        try:
            # ME-08: Riusa auth.check_and_handle_disconnect_modal invece di duplicare logica
            if self.auth.check_and_handle_disconnect_modal(self.page):
                logger.info("Heartbeat: modale disconnessione gestito da AuthManager")
                return

            # Check popup generici di dismissione
            dismiss_labels = ["Continue", "Continua", "Got It", "Ho capito"]
            for label in dismiss_labels:
                try:
                    btn = self.page.get_by_role("button", name=label)
                    if btn.count() and btn.first.is_visible(timeout=1000):
                        btn.first.click(timeout=3000)
                        self.page.wait_for_timeout(1000)
                        logger.debug(f"Heartbeat: dismiss popup '{label}'")
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Errore _handle_post_heartbeat_modals: {e}")

    def _make_status_table(self, phase: str, scanned: int, relisted: int, errors: int):
        from datetime import datetime

        from rich.table import Table

        current_time = datetime.now().strftime("%H:%M:%S")
        table = Table(title=f"FIFA Auto-Relist [🕒 {current_time}]")
        table.add_column("Fase", style="cyan")
        table.add_column("Scansionati", justify="right")
        table.add_column("Rilistati", justify="right", style="green")
        table.add_column("Errori", justify="right", style="red")
        table.add_row(phase, str(scanned), str(relisted), str(errors))
        return table

    def handle_reboot(self) -> None:
        """Riavvio completo del processo con os.execv()."""
        logger.info("🔄 Riavvio processo...")
        try:
            self.controller.stop()
        except Exception:
            pass
        # Forza kill di Chrome orfano prima di os.execv (libera il lock sul profilo)
        try:
            self.controller.force_kill_chrome()
        except Exception:
            pass
        time.sleep(2)  # Attendi che il filesystem rilasci i file del profilo
        os.execv(sys.executable, [sys.executable, sys.argv[0]])

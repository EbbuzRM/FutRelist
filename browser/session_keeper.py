from __future__ import annotations
from typing import Optional
import logging
import time
from browser.controller import BrowserController
from browser.auth import AuthManager
from browser.error_handler import ensure_session
from bot_state import BotState
from notifier import send_telegram_alert

logger = logging.getLogger(__name__)

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
        get_credentials_fn
    ):
        self.controller = controller
        self.auth = auth
        self.bot_state = bot_state
        self.page = page
        self.get_credentials = get_credentials_fn

    def ensure_session(self, timeout_ms: int = 10000) -> None:
        """Verifica e ripristina la sessione se necessaria."""
        ensure_session(self.page, self.auth, self.controller, self.get_credentials, timeout_ms=timeout_ms)

    def supervise_state(self, status_console) -> bool:
        """
        Valuta se il bot deve essere in deep sleep o pausa.
        Ritorna True se il bot è in uno stato che richiede l'attesa (console/pause).
        """
        if self.bot_state.is_console_mode():
            until = self.bot_state.get_console_mode_until()
            until_str = f" (auto-resume alle {until.strftime('%H:%M')})" if until else ""
            logger.info(f"[Console Mode] 🎮 Deep sleep{until_str} — zero interazione WebApp")
            status_console.print(self._make_status_table("🎮 Console Mode", 0, 0, 0))
            import time
            time.sleep(30)
            return True

        if self.bot_state.is_paused():
            logger.info("[Telegram] Bot in pausa — skip scanning")
            status_console.print(self._make_status_table("⏸️ In Pausa (Telegram)", 0, 0, 0))
            import time
            time.sleep(10)
            return True
            
        return False

    def wait_with_heartbeat(
        self, 
        wait_seconds: int, 
        logger_instance: logging.Logger, 
        min_heartbeat_delay: int = 150, 
        max_heartbeat_delay: int = 300
    ) -> bool:
        """
        Attesa in chunk con Heartbeat (click 'Clear Sold') per mantenere la sessione.
        Ritorna True se un reboot è stato richiesto.
        """
        import random
        waited = 0
        while waited < wait_seconds:
            remaining = wait_seconds - waited
            current_heartbeat_interval = random.randint(min_heartbeat_delay, max_heartbeat_delay)
            current_wait = min(current_heartbeat_interval, remaining)
            
            if self.bot_state.wait_interruptible(current_wait):
                return True # Reboot richiesto
                
            if self.bot_state.has_commands():
                return False # Interrotto per comandi
                
            waited += current_wait
            
            if waited < wait_seconds and not self.bot_state.is_paused() and not self.bot_state.is_console_mode():
                self._execute_heartbeat()
                
        return False

    def _execute_heartbeat(self) -> None:
        """Esegue l'azione di heartbeat cliccando 'Clear Sold'."""
        try:
            clear_btn = self.page.get_by_role("button", name="Clear Sold Items")
            if not clear_btn.count():
                clear_btn = self.page.get_by_role("button", name="Cancella oggetti venduti")
            if not clear_btn.count():
                clear_btn = self.page.locator('button:has-text("Clear Sold"), button:has-text("Cancella")')

            if clear_btn.count() and clear_btn.first.is_visible(timeout=3000):
                clear_btn.first.click(timeout=3000)
                self.page.wait_for_timeout(2000)
                
                cancel_btn = self.page.get_by_role("button", name="Cancel")
                if not cancel_btn.count():
                    cancel_btn = self.page.get_by_role("button", name="Annulla")
                if cancel_btn.count() and cancel_btn.first.is_visible(timeout=1000):
                    cancel_btn.first.click(timeout=2000)
            
            self.page.wait_for_timeout(2000)
            if self.auth.is_console_session_active(self.page):
                logger.warning("Heartbeat ha rilevato la console in uso!")
            if not self.auth.is_logged_in(self.page, timeout_ms=3000):
                logger.warning("Heartbeat ha rilevato sessione scaduta.")
        except Exception as e:
            logger.debug(f"Errore heartbeat: {e}")

    def _make_status_table(self, phase: str, scanned: int, relisted: int, errors: int):
        from rich.table import Table
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        table = Table(title=f"FIFA Auto-Relist [🕒 {current_time}]")
        table.add_column("Fase", style="cyan")
        table.add_column("Scansionati", justify="right")
        table.add_column("Rilistati", justify="right", style="green")
        table.add_column("Errori", justify="right", style="red")
        table.add_row(phase, str(scanned), str(relisted), str(errors))
        return table

    def handle_reboot(self, controller: BrowserController, notifications_config) -> None:
        """
        Gestisce la procedura di reboot: notifica, chiusura browser e reset evento.
        """
        logger.info("Esecuzione procedura di reboot...")
        send_telegram_alert(notifications_config, "🔄 Reboot richiesto: riavvio in corso...")
        controller.stop()
        self.bot_state.clear_reboot_event()

    def handle_critical_error(self, error: Exception, notifications_config) -> None:
        """
        Gestisce l'errore critico all'avvio o durante l'esecuzione.
        """
        logger.exception(f"Errore critico: {error}")
        send_telegram_alert(notifications_config, f"🚨 Errore critico: {error}. Riavvio tra 30s...")
        time.sleep(30)

from __future__ import annotations
from typing import Optional, Dict, Any
import logging
import os
import random
import sys
import time
from datetime import datetime
from browser.controller import BrowserController
from browser.auth import AuthManager
from browser.error_handler import ensure_session
from bot_state import BotState, RebootRequestError
from notifier import send_telegram_alert, send_telegram_error_with_screenshot

logger = logging.getLogger(__name__)

class SessionKeeper:
    """
    Gestisce la supervisione della sessione browser:
    - Heartbeat per mantenere la sessione attiva
    - Gestione della modalità Console (deep sleep) e Pausa
    - Attese interruttibili da comandi Telegram
    - Gestione del riavvio completo del processo con os.execv()
    """
    def __init__(
        self, 
        controller: BrowserController, 
        auth: AuthManager, 
        bot_state: BotState, 
        page, 
        get_credentials_fn,
        notifications_config
    ):
        self.controller = controller
        self.auth = auth
        self.bot_state = bot_state
        self.page = page
        self.get_credentials = get_credentials_fn
        self.notifications_config = notifications_config

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
            self.bot_state.wait_interruptible(300)  # 5 minuti; si sveglia subito su /reboot
            return True

        if self.bot_state.is_paused():
            until = self.bot_state.get_pause_until()
            until_str = f" (auto-resume alle {until.strftime('%H:%M')})" if until else ""
            logger.info(f"[Telegram] Bot in pausa{until_str} — skip scanning")
            status_console.print(self._make_status_table(f"⏸️ In Pausa (Telegram){until_str}", 0, 0, 0))
            self.bot_state.wait_interruptible(300)  # 5 minuti; si sveglia subito su /resume o /reboot
            return True
        
        return False

    def wait_with_heartbeat(self, wait_seconds: float, logger: logging.Logger, deadline: datetime | None = None) -> bool:
        """
        Attende per il tempo specificato con heartbeat periodico e controllo deadline.
        
        Args:
            wait_seconds: Secondi da attendere
            logger: Logger per registrare le operazioni
            deadline: Timestamp di deadline per uscita anticipata
            
        Returns:
            True se il reboot è stato richiesto, False altrimenti
        """
        start_time = datetime.now()
        total_waited = 0.0
        
        while total_waited < wait_seconds:
            # Calcola il tempo rimanente per questo chunk
            remaining_wait = wait_seconds - total_waited
            
            # Se c'è una deadline, calcola il tempo rimanente rispetto ad essa
            if deadline:
                time_to_deadline = (deadline - datetime.now()).total_seconds()
                if time_to_deadline <= 0:
                    logger.info("Deadline raggiunta, uscita anticipata dall'attesa")
                    return False  # Deadline raggiunta, non è un reboot
                # Limita l'attesa al tempo rimanente alla deadline
                chunk_wait = min(remaining_wait, time_to_deadline)
            else:
                chunk_wait = remaining_wait
            
            # Esegui heartbeat e attesa interruttibile
            if chunk_wait > 0:
                # Esegui heartbeat ogni 2.5-5 minuti
                heartbeat_interval = random.uniform(150, 300)  # 2.5-5 minuti
                
                if chunk_wait >= heartbeat_interval:
                    # Esegui heartbeat prima dell'attesa lunga
                    self._perform_heartbeat(logger)
                    # Attesa a chunk
                    if self.bot_state.wait_interruptible(heartbeat_interval):
                        return True  # Reboot richiesto
                    total_waited += heartbeat_interval
                else:
                    # Attesa corta senza heartbeat
                    if self.bot_state.wait_interruptible(chunk_wait):
                        return True  # Reboot richiesto
                    total_waited += chunk_wait
            
            # Controlla se il reboot è stato richiesto
            if self.bot_state.is_reboot_requested():
                logger.info("Reboot richiesto durante l'attesa")
                return True
        
        logger.debug(f"Attesa completata: {total_waited:.1f}s su {wait_seconds}s")
        return False  # Nessun reboot richiesto

    def _perform_heartbeat(self, logger: logging.Logger) -> None:
        """
        Esegue un heartbeat per mantenere la sessione attiva.
        
        Args:
            logger: Logger per registrare l'operazione
        """
        try:
            logger.debug("Esecuzione heartbeat...")
            # Click sulla tab 'Transfers' per mantenere la sessione attiva
            # Questo è il nuovo heartbeat che sostituisce 'Clear Sold'
            self.page.click("text=Transfers", timeout=5000)
            logger.debug("Heartbeat eseguito con successo")
        except Exception as e:
            logger.warning(f"Heartbeat fallito: {e}")
            # Non è critico, il controller gestirà il recovery

    def handle_critical_error(self, error: Exception, notifications_config: Dict[str, Any]) -> None:
        """
        Gestisce gli errori critici e tenta un riavvio del processo.
        
        Args:
            error: L'eccezione che ha causato l'errore critico
            notifications_config: Configurazioni per le notifiche Telegram
        """
        logger.error(f"🚨 Errore critico rilevato: {type(error).__name__}: {error}")
        
        # Invia notifica di errore
        try:
            send_telegram_error_with_screenshot(
                notifications_config,
                f"🚨 Errore critico: {type(error).__name__}: {error}. Riavvio in corso...",
                page=self.page
            )
        except Exception as notification_error:
            logger.error(f"⚠️ Impossibile inviare notifica di errore: {notification_error}")
        
        # Attendi un po' prima del riavvio per permettere alla notifica di essere inviata
        logger.info("⏳ attesa 3 secondi prima del riavvio...")
        time.sleep(3)
        
        # Esegui il riavvio
        self.handle_reboot(self.controller, notifications_config)

    def handle_reboot(self, controller: BrowserController, notifications_config: Dict[str, Any]) -> None:
        """
        Gestisce il riavvio completo del processo usando os.execv().
        
        Sostituisce completamente il processo corrente con un nuovo processo Python
        che esegue lo stesso script, mantenendo tutte le configurazioni necessarie.
        
        Args:
            controller: Istanza BrowserController per la pulizia della sessione
            notifications_config: Configurazioni per le notifiche Telegram
        """
        logger.info("🔄 Inizio riavvio del processo...")
        
        try:
            # Pulisci la sessione prima del reboot
            logger.info("🧹 Pulizia sessione pre-reboot...")
            controller.stop()
            
        except Exception as e:
            logger.error(f"⚠️ Errore durante la pulizia della sessione: {e}")
        
        # Prepara le variabili d'ambiente per il nuovo processo
        env = os.environ.copy()
        
        # Passa le configurazioni necessarie come variabili d'ambiente
        if notifications_config:
            env['FIFA_TELEGRAM_TOKEN'] = notifications_config.get('telegram_token', '')
            env['FIFA_TELEGRAM_CHAT_ID'] = notifications_config.get('telegram_chat_id', '')
        
        # Passa altre variabili d'ambiente necessarie
        env['PYTHONPATH'] = os.getcwd()
        
        # Costruisci il comando per il nuovo processo
        python_executable = sys.executable
        script_path = os.path.abspath(__file__)
        
        # Cambia directory alla radice del progetto
        os.chdir(os.path.dirname(os.path.dirname(script_path)))
        
        logger.info(f"🔄 Riavvio processo: {python_executable} {script_path}")
        logger.info(f"🔧 Variabili d'ambiente passate: {len(env)} configurazioni")
        
        try:
            # Sostituisci completamente il processo corrente
            os.execv(python_executable, [python_executable, script_path])
            
        except Exception as e:
            logger.error(f"❌ Errore durante il riavvio con os.execv(): {e}")
            logger.info("⚠️ Fallback: tentativo di riavvio normale...")
            
            # Se os.execv fallisce, esegui un fallback con subprocess
            try:
                import subprocess
                subprocess.run([python_executable, script_path], env=env)
                sys.exit(0)
            except Exception as fallback_error:
                logger.error(f"❌ Fallback fallito: {fallback_error}")
                sys.exit(1)

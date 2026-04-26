"""
FIFA 26 Auto-Relist Tool
Refactored Entrypoint
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from browser.controller import BrowserController
from browser.auth import AuthManager
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
from browser.relist import RelistExecutor
from browser.rate_limiter import RateLimiter
from bot_state import BotState, RebootRequestError
from telegram_handler import TelegramHandler
from browser.sold_handler import SoldHandler
from config.config import ConfigManager
from config.log_config import setup_logging
from browser.session_keeper import SessionKeeper
from logic.relist_engine import RelistEngine, ConsoleSessionError
from core.notification_batch import NotificationBatch
from notifier import send_telegram_alert

def get_credentials() -> tuple[str, str]:
    email = os.environ.get("FIFA_EMAIL")
    password = os.environ.get("FIFA_PASSWORD")
    if email and password:
        return email, password
    raise RuntimeError("Credenziali FIFA_EMAIL o FIFA_PASSWORD non trovate nel file .env")

def authenticate(controller, auth, page) -> None:
    from browser.auth import AuthError
    logger = logging.getLogger(__name__)
    if auth.has_saved_session():
        page.wait_for_timeout(2000)
    
    while True:
        # Controlla se siamo su signin.ea.com (dopo un modale di disconnessione)
        current_url = page.url.lower()
        if "signin.ea.com" in current_url:
            logger.info("Rilevato signin.ea.com, procedo con login diretto...")
            # Siamo già sulla pagina di login EA, skip del bottone "Login" della WebApp
            email, password = get_credentials()
            if auth.perform_login(page, email, password):
                auth.save_session(controller.context)
                return
            # Se fallisce, riprova dal loop
            page.wait_for_timeout(3000)
            continue
        
        if auth.is_console_session_active(page):
            logger.warning("Sessione console attiva. Attesa...")
            time.sleep(1800)
            controller.navigate_to_webapp()
            page.wait_for_timeout(5000)
            login_btn = page.get_by_role("button", name="Login")
            if login_btn.count():
                login_btn.first.click(timeout=5000)
                page.wait_for_timeout(5000)
        
        if auth.is_logged_in(page, timeout_ms=5000):
            auth.save_session(controller.context)
            return

        email, password = get_credentials()
        if auth.perform_login(page, email, password):
            auth.save_session(controller.context)
            return
        if auth.is_console_session_active(page):
            continue
        raise AuthError("Login fallito")

def main() -> None:
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    fifa_logger = logging.getLogger("fifa")
    status_console = Console()

    cm = ConfigManager()
    app_config = cm.load()
    config = app_config.to_dict()

    bot_state = BotState()
    telegram: TelegramHandler | None = None

    while True:
        try:
            controller = BrowserController(config)
            auth = AuthManager(config)
            profile_dir = auth.load_session()
            page = controller.start(user_data_dir=profile_dir)
            controller.navigate_to_webapp()
            authenticate(controller, auth, page)

            navigator = TransferMarketNavigator(page, config)
            detector = ListingDetector(page)
            executor = RelistExecutor(page, config)
            rate_limiter = RateLimiter(
                min_delay_ms=app_config.rate_limiting.min_delay_ms,
                max_delay_ms=app_config.rate_limiting.max_delay_ms,
            )

            keeper = SessionKeeper(controller, auth, bot_state, page, get_credentials)
            engine = RelistEngine(page, config, navigator, detector, executor, auth, bot_state)
            batch = NotificationBatch()

            if app_config.notifications.telegram_token:
                telegram = TelegramHandler(
                    token=app_config.notifications.telegram_token,
                    chat_id=app_config.notifications.telegram_chat_id,
                    bot_state=bot_state,
                    page=page,
                    log_dir=Path(__file__).parent / "logs",
                )
                telegram.set_sold_handler(SoldHandler(page, config))
                telegram.start()
            else:
                telegram = None

            # Conferma avvio sessione (sia all'inizio che dopo reboot)
            send_telegram_alert(app_config.notifications, "✅ Bot avviato e pronto!")

            cycle = 0
            while True:
                cycle += 1
                bot_state.update_stats(cycle=1)
                
                if keeper.supervise_state(status_console):
                    continue

                if bot_state.is_reboot_requested():
                    break

                while bot_state.has_commands():
                    cmd = bot_state.get_next_command()
                    if not cmd:
                        continue
                        
                    if cmd.get("type") == "del_sold":
                        res = cmd.get("callback")()
                        send_telegram_alert(app_config.notifications, f"🧹 Pulizia: {res.items_cleared} oggetti")
                    elif cmd.get("type") == "screenshot":
                        cmd.get("callback")()

                keeper.ensure_session()

                try:
                    succeeded, failed, next_wait = engine.process_cycle(cycle, keeper)
                    # stats are now updated inside engine.process_cycle to avoid race conditions with manual relist detection
                    scan_result = detector.scan_listings()
                    batch.accumulate(scan_result, succeeded, failed)

                    if batch.is_ready_to_flush(next_wait):
                        batch.flush(app_config, page, logger, scan_result)

                    rate_limiter.wait()
                    if keeper.wait_with_heartbeat(next_wait, logger):
                        break # Reboot

                except RebootRequestError:
                    # Inviato dal golden loop o dal supervisor per forzare un riavvio dolce
                    logger.info("Ricevuta richiesta di Reboot interno asincrono.")
                    break
                except InterruptedError:
                    # This normally means Ctrl+C or a fatal signal to stop the whole app
                    controller.stop()
                    return

            # Inner loop broke (Reboot requested or heartbeat reboot)
            if telegram:
                telegram.stop()
            keeper.handle_reboot(controller, app_config.notifications)
        
        except ConsoleSessionError:
            logger.warning("Terminazione forzata del ciclo per Console attiva. Preparazione riavvio silente...")
            try:
                if telegram:
                    telegram.stop()
                controller.stop()
            except:
                pass
            continue
            
        except Exception as e:
            if 'keeper' in locals():
                keeper.handle_critical_error(e, app_config.notifications)
            else:
                logger.exception(f"Errore critico prima dell'inizializzazione del keeper: {e}")
                send_telegram_alert(app_config.notifications, f"🚨 Errore critico: {e}. Riavvio tra 30s...")
                time.sleep(30)
            
            try:
                if telegram:
                    telegram.stop()
                controller.stop()
            except:
                pass


if __name__ == "__main__":
    main()

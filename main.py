"""
FIFA 26 Auto-Relist Tool
Refactored Entrypoint
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import suppress
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from bot_state import BotState, RebootRequestError
from browser.auth import AuthManager
from browser.controller import BrowserController
from browser.detector import ListingDetector
from browser.navigator import TransferMarketNavigator
from browser.rate_limiter import RateLimiter
from browser.relist import RelistExecutor
from browser.session_keeper import SessionKeeper
from browser.sold_handler import SoldHandler
from config.config import ConfigManager
from config.log_config import setup_logging
from core.notification_batch import NotificationBatch
from logic.relist_engine import ConsoleSessionError, RelistEngine
from notifier import send_telegram_alert, send_telegram_error_with_screenshot
from telegram_handler import TelegramHandler


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
        if auth.is_console_session_active(page):
            logger.warning("Sessione console attiva. Attesa...")
            time.sleep(1800)
            controller.navigate_to_webapp()
            page.wait_for_timeout(5000)

            # Attendi che il click-shield scompaia prima di cliccare Login
            auth.wait_for_click_shield(page, timeout_ms=15000)

            login_btn = page.get_by_role("button", name="Login")
            if login_btn.count():
                # Retry con gestione shield (come perform_login)
                for attempt in range(1, 4):
                    try:
                        login_btn.first.click(timeout=10000)
                        break
                    except Exception as e:
                        err_msg = str(e)
                        logger.warning(f"Click Login fallito in authenticate (tentativo {attempt}): {e}")
                        if "intercepts pointer events" in err_msg or "ut-click-shield" in err_msg:
                            auth.wait_for_click_shield(page, timeout_ms=10000)
                        # Fallback: click via JavaScript (SEMPRE tentato)
                        try:
                            clicked = page.evaluate(
                                "el = document.querySelector('.btn-standard.primary'); if (el) { el.click(); return true; } return false;"
                            )
                            if clicked:
                                break
                        except Exception:
                            pass
                        # Fallback: force click (SEMPRE tentato)
                        try:
                            login_btn.first.click(timeout=5000, force=True)
                            break
                        except Exception:
                            if attempt < 3:
                                page.wait_for_timeout(3000)
                                auth.wait_for_click_shield(page, timeout_ms=10000)
                            else:
                                logger.error("Impossibile cliccare Login dopo 3 tentativi in authenticate")
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

            # Create a single RateLimiter instance to be shared across modules
            rate_limiter = RateLimiter(
                min_delay_ms=app_config.rate_limiting.min_delay_ms,
                max_delay_ms=app_config.rate_limiting.max_delay_ms,
            )
            navigator = TransferMarketNavigator(page, config, rate_limiter)
            detector = ListingDetector(page)
            executor = RelistExecutor(page, config, rate_limiter, auth)

            keeper = SessionKeeper(controller, auth, bot_state, page, get_credentials, app_config.notifications)
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
                telegram.set_sold_handler(SoldHandler(page, config, rate_limiter, navigator=navigator))
                telegram.start()
            else:
                telegram = None

            # Nota: nessuna notifica di avvio qui — l'utente riceve solo il
            # report batch al termine del relist (batch.flush). Evita spam
            # ad ogni reboot automatico.

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
                    cmd_type = cmd.get("type")
                    callback = cmd.get("callback")
                    if not callable(callback):
                        logger.warning(f"Comando con callback non valido ignorato: {cmd}")
                        continue
                    try:
                        if cmd_type == "del_sold":
                            res = callback()
                            send_telegram_alert(app_config.notifications, f"🧹 Pulizia: {res.items_cleared} oggetti")
                        elif cmd_type == "screenshot":
                            callback()
                        else:
                            logger.warning(f"Tipo di comando sconosciuto: {cmd_type}")
                    except Exception as e:
                        logger.error(f"Errore nel processing del comando Telegram {cmd_type}: {e}")
                        send_telegram_alert(app_config.notifications, f"❌ Comando /{cmd_type} fallito: {e}")

                keeper.ensure_session()

                try:
                    succeeded, failed, next_wait, scan_result, deadline, expired_count = engine.process_cycle()
                    batch.accumulate(scan_result, succeeded, failed, expired_count)

                    # Flush solo se le condizioni di batch sono soddisfatte
                    # (ondata finita, max cicli, o timeout dall'ultimo flush)
                    if batch.is_ready_to_flush(next_wait):
                        batch.flush_if_any(app_config, page, logger, scan_result)

                    rate_limiter.wait()
                    if keeper.wait_with_heartbeat(next_wait, logger, deadline=deadline):
                        break  # Reboot

                except RebootRequestError:
                    # Inviato dal golden loop o dal supervisor per forzare un riavvio dolce
                    logger.info("Ricevuta richiesta di Reboot interno asincrono.")
                    batch.flush_if_any(app_config, page, logger, locals().get("scan_result"), force=True)
                    break
                except InterruptedError:
                    # This normally means Ctrl+C or a fatal signal to stop the whole app
                    controller.stop()
                    batch.flush_if_any(app_config, page, logger, None, force=True)
                    return

            # Inner loop broke (Reboot requested or heartbeat reboot)
            if telegram:
                telegram.stop()
            batch.flush_if_any(app_config, page, logger, locals().get("scan_result"), force=True)
            keeper.handle_reboot()

        except ConsoleSessionError:
            logger.warning("Terminazione forzata del ciclo per Console attiva. Preparazione riavvio silente...")
            from notifier import send_telegram_emergency_alert

            send_telegram_emergency_alert(
                app_config.notifications, "🎮 Console session rilevata — bot in pausa per prevenire ban risk."
            )
            try:
                if telegram:
                    telegram.stop()
                controller.stop()
            except Exception:
                pass
            continue

        except (MemoryError, RecursionError) as e:
            # Errori fatali: reboot inutile, termina il processo
            err_msg = f"🚨 ERRORE FATALE ({type(e).__name__}): {e}. Processo terminato."
            logger.critical(err_msg)
            try:
                batch.flush_if_any(app_config, page, logger, None, force=True)
                send_telegram_alert(app_config.notifications, err_msg)
            except Exception:
                pass
            try:
                if telegram:
                    telegram.stop()
                controller.stop()
            except Exception:
                pass
            sys.exit(1)

        except Exception as e:
            logger.exception(f"Errore critico: {e}")
            page_ref = page if "page" in locals() else None
            scan_ref = locals().get("scan_result")
            send_telegram_error_with_screenshot(
                app_config.notifications, f"🚨 Errore critico: {e}. Riavvio in corso...", page=page_ref
            )
            time.sleep(10)

            with suppress(Exception):
                batch.flush_if_any(app_config, page_ref, logger, scan_ref, force=True)

            try:
                if telegram:
                    telegram.stop()
                controller.stop()
            except Exception:
                pass

            # Forza kill Chrome orfano + attendi unlock profilo prima di os.execv
            with suppress(Exception):
                controller.force_kill_chrome()
            time.sleep(3)

            # os.execv per garantire reload completo dei moduli (evita moduli stale in memoria)
            logger.info("Riavvio processo via os.execv dopo errore critico...")
            os.execv(sys.executable, [sys.executable, sys.argv[0]])


if __name__ == "__main__":
    main()

"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from browser.controller import BrowserController
from browser.auth import AuthManager, AuthError
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
from browser.relist import RelistExecutor
from browser.rate_limiter import RateLimiter
from browser.error_handler import ensure_session
from config.config import ConfigManager
from models.action_log import JsonFormatter
from models.listing import ListingState
from v2_relist_logic import implementazione_nuova_logica

action_logger = logging.getLogger("actions")


def setup_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

    # Dedicated actions logger: structured JSON to logs/actions.jsonl
    actions_file_handler = logging.FileHandler(
        log_dir / "actions.jsonl", mode="a", encoding="utf-8"
    )
    actions_file_handler.setLevel(logging.INFO)
    actions_file_handler.setFormatter(JsonFormatter())
    action_logger.setLevel(logging.INFO)
    action_logger.addHandler(actions_file_handler)
    action_logger.propagate = False


def make_status_table(phase: str, scanned: int, relisted: int, errors: int) -> Table:
    current_time = datetime.now().strftime("%H:%M:%S")
    table = Table(title=f"FIFA Auto-Relist [🕒 {current_time}]")
    table.add_column("Fase", style="cyan")
    table.add_column("Scansionati", justify="right")
    table.add_column("Rilistati", justify="right", style="green")
    table.add_column("Errori", justify="right", style="red")
    table.add_row(phase, str(scanned), str(relisted), str(errors))
    return table


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("FIFA_EMAIL")
    password = os.environ.get("FIFA_PASSWORD")

    if email and password:
        return email, password

    raise RuntimeError("Credenziali FIFA_EMAIL o FIFA_PASSWORD non trovate nel file .env")


def authenticate(controller, auth, page) -> None:
    """Gestisce il flusso di login o ripristino sessione. Solleva AuthError su fallimento.

    Se la WebApp mostra 'Signed Into Another Device' (sessione PS5/console attiva),
    aspetta pazientemente in loop invece di andare in crash.
    """
    logger = logging.getLogger(__name__)

    if auth.has_saved_session():
        logger.info("Sessione salvata trovata, verifica in corso...")
        page.wait_for_timeout(2000)

    # --- Gestione sessione console e Login ---
    # EA a volte droppa la sessione dopo ore di inattività mostrandoci solo la landing page
    # (senza l'errore palese "Signed into another device"). Cliccando Login, se l'utente 
    # sta ancora giocando, l'errore ricompare istantaneamente. Serviva un loop generale protettivo.
    CONSOLE_WAIT_SECONDS = 1800   # controlla ogni 30 minuti
    MAX_CONSOLE_WAIT_HOURS = 4  # aspetta al massimo 4 ore
    max_console_checks = (MAX_CONSOLE_WAIT_HOURS * 3600) // CONSOLE_WAIT_SECONDS
    console_checks = 0

    while True:
        # FASE 1: Pura attesa console attiva
        while auth.is_console_session_active(page):
            console_checks += 1
            waited_min = (console_checks * CONSOLE_WAIT_SECONDS) // 60
            logger.warning(
                f"[Console attiva] Sessione PS5/Console in uso. "
                f"Riprovo tra {CONSOLE_WAIT_SECONDS}s... "
                f"(attesa totale: ~{waited_min} min)"
            )
            if console_checks >= max_console_checks:
                raise AuthError(
                    f"Sessione console ancora attiva dopo {MAX_CONSOLE_WAIT_HOURS}h. "
                    "Esci da Ultimate Team sulla console e riavvia il bot."
                )
            time.sleep(CONSOLE_WAIT_SECONDS)
            
            logger.info("Ricarico la WebApp per ricontrollare lo stato della console...")
            controller.navigate_to_webapp()
            page.wait_for_timeout(5000)

            # Contromisura al session drop: EA ci farà scendere sulla Landing page generica.
            # Se ricaricando troviamo il tasto Login (invece dell'errore), lo premiamo per 
            # generare l'esito reale: "Siamo loggati" o "La console è ancora occupata".
            login_btn = page.get_by_role("button", name="Login")
            if login_btn.count():
                logger.info("Pulsante Login trovato (Landing Page). Click per verificare stato console...")
                login_btn.first.click()
                # Aspettiamo 5 secondi invece di 8, se è console occupata il pop-up appare subito
                page.wait_for_timeout(5000)

        # FASE 2: La console non mostra allarmi attivi. Vediamo se siamo già attivamente loggati
        if auth.is_logged_in(page, timeout_ms=5000):
            logger.info("Già loggato con sessione salvata (o ripristino automatico riuscito).")
            auth.save_session(controller.context)
            return

        # FASE 3: Procedi con il login manuale formale
        url = page.url.lower()
        if "signin.ea.com" in url:
            logger.info("Reindirizzamento automatico alla pagina di login EA rilevato")
        else:
            logger.info("Login richiesto dalla landing page...")
            if not auth.wait_for_login_page(page, timeout=10000):
                logger.warning("Pulsante Login non rilevato, provo comunque ad andare avanti...")

        email, password = get_credentials()
        
        # Facciamo finta che l'esito sia booleano. Se fallisce, verifichiamo il perché.
        success = auth.perform_login(page, email, password)

        if success:
            auth.save_session(controller.context)
            logger.info("Login completato e sessione salvata")
            return
        else:
            # Se ha fallito potremmo aver appena riscoperto la sessione console annidata post-login
            if auth.is_console_session_active(page):
                logger.warning("Rilevata sessione console attiva ORA, in fase di login formale. Riprendo ad attendere...")
                continue # Torna al "while True" e rientra nel "while auth.is_console_session_active"
            
            # Se ha fallito e non è colpa della console... è un errore puro (credenziali o caricamento)
            raise AuthError("Login fallito (non a causa della console)")


def navigate_with_retry(navigator, page) -> bool:
    """Naviga al Transfer List con un retry su timeout."""
    logger = logging.getLogger(__name__)

    try:
        return navigator.go_to_transfer_list()
    except Exception as e:
        logger.warning(f"Timeout navigazione, riprovo: {e}")
        page.reload()
        page.wait_for_timeout(3000)
        try:
            return navigator.go_to_transfer_list()
        except Exception as e2:
            logger.error(f"Secondo tentativo fallito: {e2}")
            return False


def relist_expired_listings(executor, expired_listings) -> tuple[int, int]:
    """Esegue il rilist dei listing scaduti e logga ogni azione. Ritorna (succeeded, failed)."""
    logger = logging.getLogger(__name__)
    succeeded = 0
    failed = 0
    total = len(expired_listings)

    for listing in expired_listings:
        result = executor.relist_single(listing)
        if result.success:
            succeeded += 1
            action_logger.info(
                "Rilist completato",
                extra={"action": "relist", "player_name": result.player_name, "success": True},
            )
        else:
            failed += 1
            action_logger.warning(
                "Rilist fallito",
                extra={"action": "relist", "player_name": result.player_name, "success": False, "error": result.error},
            )
        logger.info(f"Progresso Rilist: {succeeded + failed}/{total}")

    return succeeded, failed


def main() -> None:
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")

    controller = None
    app_config = None

    try:
        cm = ConfigManager()
        app_config = cm.load()
        config = app_config.to_dict()
        logger.info(f"Config caricata (intervallo: {app_config.scan_interval_seconds}s, modalità: {app_config.listing_defaults.relist_mode})")

        from notifier import send_telegram_alert
        send_telegram_alert(app_config.notifications, "✅ FIFA 26 Auto-Relist Tool avviato con successo! Notifiche Telegram attivate.")

        controller = BrowserController(config)
        auth = AuthManager(config)
        
        # Prova a ripristinare il profilo browser esistente
        profile_dir = auth.load_session()
        page = controller.start(user_data_dir=profile_dir)

        controller.navigate_to_webapp()
        logger.info(f"WebApp caricata: {page.title()}")

        authenticate(controller, auth, page)
        logger.info("=== Autenticazione completata ===")

        navigator = TransferMarketNavigator(page, config)
        detector = ListingDetector(page)
        executor = RelistExecutor(page, config)
        rate_limiter = RateLimiter(
            min_delay_ms=app_config.rate_limiting.min_delay_ms,
            max_delay_ms=app_config.rate_limiting.max_delay_ms,
        )
        scan_interval = app_config.scan_interval_seconds
        cycle = 0

        logger.info(f"Avvio loop continuo (intervallo: {scan_interval}s). Premi Ctrl+C per fermare.")

        status_console = Console()
        
        while True:
            cycle += 1
            logger.info(f"=== Ciclo {cycle} ===")

            ensure_session(page, auth, controller, get_credentials)

            # Gestione sessione PS5/Console attiva nel loop
            if auth.is_console_session_active(page):
                wait_console = 1800 # 30 minuti
                logger.info(f"Sessione console rilevata. Sospendo per {wait_console}s...")
                status_console.print(make_status_table("Console Attiva", 0, 0, 0))
                time.sleep(wait_console)
                page.reload() # Ricarica per vedere se la sessione è libera
                continue

            if not navigate_with_retry(navigator, page):
                status_console.print(make_status_table("Errore Navigazione", 0, 0, 0))
                rate_limiter.wait()
                continue

            # --- Pre-navigazione: attesa di precisione fino al sync_minute ---
            sync_minute_prenav = app_config.listing_defaults.sync_minute_offset
            if sync_minute_prenav is not None:
                now_pre = datetime.now()
                early_minute = (sync_minute_prenav - 1) % 60
                if now_pre.minute == early_minute:
                    wait_precision = 60 - now_pre.second
                    if wait_precision > 0:
                        logger.info(f"Pre-nav completata! Attesa di precisione: {wait_precision}s fino al minuto {sync_minute_prenav}...")
                        time.sleep(wait_precision)
                    logger.info(f"Minuto {sync_minute_prenav} raggiunto! Scansione...")

            next_wait = implementazione_nuova_logica(
                page, detector, executor, app_config,
                cycle, status_console, make_status_table,
                relist_expired_listings,
            )

            logger.info(f"Prossimo ciclo tra {next_wait}s...")
            rate_limiter.wait()
            time.sleep(next_wait)

    except AuthError as e:
        logger.error(f"Errore autenticazione: {e}")
        if app_config:
            from notifier import send_telegram_alert
            send_telegram_alert(app_config.notifications, f"🚨 ERRORE FIFA BOT:\n{e}")
        if controller and controller.is_running():
            controller.stop()
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interruzione utente")
        if controller and controller.is_running():
            controller.stop()
    except Exception as e:
        logger.error(f"Errore: {e}", exc_info=True)
        if app_config:
            from notifier import send_telegram_alert
            send_telegram_alert(app_config.notifications, f"❌ ERRORE CRITICO INATTESO:\n{e}")
        if controller and controller.is_running():
            controller.stop()
        sys.exit(1)


def build_parser():
    """Build CLI argument parser with run and config subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="fifa-relist",
        description="FIFA 26 Auto-Relist Tool",
    )
    sub = parser.add_subparsers(dest="command")

    # run (default)
    sub.add_parser("run", help="Start the auto-relist tool")

    # config
    config_parser = sub.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_action")

    config_sub.add_parser("show", help="Display current settings")

    set_parser = config_sub.add_parser("set", help="Update a setting")
    set_parser.add_argument("key", help="Dotted key (e.g., listing_defaults.duration)")
    set_parser.add_argument("value", help="New value")

    config_sub.add_parser("reset", help="Reset all settings to defaults")

    # history
    history_parser = sub.add_parser("history", help="Mostra cronologia azioni")
    history_parser.add_argument(
        "-n", "--lines", type=int, default=20, help="Numero di voci da mostrare"
    )

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "config":
        from config.config import ConfigManager

        cm = ConfigManager()
        if args.config_action == "show":
            cfg = cm.load()
            print(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False))
        elif args.config_action == "set":
            cm.set_value(args.key, args.value)
            print(f"OK: {args.key} = {args.value}")
        elif args.config_action == "reset":
            cm.reset_defaults()
            print("OK: Config reset to defaults")
        else:
            parser.parse_args(["config", "--help"])
    elif args.command == "history":
        from models.action_log import parse_action_history

        log_path = Path(__file__).parent / "logs" / "actions.jsonl"
        entries = parse_action_history(log_path, args.lines)

        if not entries:
            print("Nessuna cronologia azioni trovata.")
        else:
            for entry in entries:
                ts = entry.get("timestamp", "?")
                success = entry.get("success", False)
                indicator = "OK" if success else "ERR"
                message = entry.get("message", "")
                player = entry.get("player_name")
                if player:
                    print(f"[{ts}] {indicator} {message} - {player}")
                else:
                    print(f"[{ts}] {indicator} {message}")
    else:
        main()

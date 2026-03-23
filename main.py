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
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.table import Table

from browser.controller import BrowserController
from browser.auth import AuthManager, AuthError
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
from browser.relist import RelistExecutor
from browser.rate_limiter import RateLimiter
from browser.error_handler import ensure_session, retry_on_timeout
from config.config import ConfigManager, AppConfig
from models.action_log import JsonFormatter

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
        logging.Formatter("[%(levelname)s] %(message)s")
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
    table = Table(title="FIFA Auto-Relist")
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

    print("\n=== Credenziali FIFA 26 ===")
    email = input("Email EA: ").strip()
    password = input("Password EA: ").strip()

    return email, password


def authenticate(controller, auth, page) -> None:
    """Gestisce il flusso di login o ripristino sessione. Solleva AuthError su fallimento."""
    logger = logging.getLogger(__name__)

    if auth.has_saved_session():
        logger.info("Sessione salvata trovata, tentativo di ripristino...")
        auth.load_session(controller.context)
        page.reload()
        page.wait_for_timeout(3000)

    if auth.is_logged_in(page):
        logger.info("Già loggato con sessione salvata")
        return

    logger.info("Login richiesto...")

    if not auth.wait_for_login_page(page):
        raise AuthError("Pagina di login non trovata")

    email, password = get_credentials()

    if not auth.perform_login(page, email, password):
        raise AuthError("Login fallito")

    auth.save_session(controller.context)
    logger.info("Login completato e sessione salvata")


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


def relist_expired_listings(executor, expired_listings, live, status_label, total_count) -> tuple[int, int]:
    """Esegue il rilist dei listing scaduti e logga ogni azione. Ritorna (succeeded, failed)."""
    logger = logging.getLogger(__name__)
    succeeded = 0
    failed = 0

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
        live.update(make_status_table(status_label, total_count, succeeded, failed))

    return succeeded, failed


def main() -> None:
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")

    controller = None

    try:
        cm = ConfigManager()
        app_config = cm.load()
        config = app_config.to_dict()
        logger.info(f"Config caricata (scan interval: {app_config.scan_interval_seconds}s)")

        controller = BrowserController(config)
        auth = AuthManager(config)
        page = controller.start()

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

        live_console = Console(stderr=True)
        with Live(make_status_table("In attesa...", 0, 0, 0), refresh_per_second=2, console=live_console) as live:
            while True:
                cycle += 1
                logger.info(f"=== Ciclo {cycle} ===")

                ensure_session(page, auth, controller, get_credentials)

                live.update(make_status_table("Navigazione...", 0, 0, 0))
                if not navigate_with_retry(navigator, page):
                    live.update(make_status_table("Errore", 0, 0, 0))
                    rate_limiter.wait()
                    continue

                live.update(make_status_table("Scansione...", 0, 0, 0))
                scan_result = detector.scan_listings()
                label = f"Ciclo {cycle}"

                if scan_result.is_empty:
                    logger.info("Nessun listing trovato")
                    live.update(make_status_table(label, 0, 0, 0))
                else:
                    logger.info(f"Scan: {scan_result.total_count} listing (attivi={scan_result.active_count}, scaduti={scan_result.expired_count}, venduti={scan_result.sold_count})")

                    if scan_result.expired_count > 0:
                        expired = [l for l in scan_result.listings if l.needs_relist]
                        succeeded, failed = relist_expired_listings(
                            executor, expired, live, f"{label} - Rilist", scan_result.total_count,
                        )
                        action_logger.info("Batch completato", extra={"action": "batch", "success": True, "total": succeeded + failed, "succeeded": succeeded})
                        logger.info(f"Rilist completato: {succeeded}/{succeeded + failed} successi")
                        live.update(make_status_table(f"{label} - OK", scan_result.total_count, succeeded, failed))
                    else:
                        logger.info("Nessun listing scaduto")
                        live.update(make_status_table(label, scan_result.total_count, 0, 0))

                logger.info(f"Prossimo ciclo tra {scan_interval}s...")
                rate_limiter.wait()
                time.sleep(scan_interval)

        cm.save()
        input("\nPremi INVIO per chiudere il browser...")
        controller.stop()

    except AuthError as e:
        logger.error(f"Errore autenticazione: {e}")
        if controller and controller.is_running():
            controller.stop()
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interruzione utente")
        if controller and controller.is_running():
            controller.stop()
    except Exception as e:
        logger.error(f"Errore: {e}", exc_info=True)
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

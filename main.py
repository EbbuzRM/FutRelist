"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.table import Table

from browser.controller import BrowserController
from browser.auth import AuthManager
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
        logger.info("Config caricata")
        logger.info(f"Scan interval: {app_config.scan_interval_seconds}s")

        controller = BrowserController(config)
        auth = AuthManager(config)

        page = controller.start()

        controller.navigate_to_webapp()
        logger.info(f"WebApp caricata: {page.title()}")

        if auth.has_saved_session():
            logger.info("Sessione salvata trovata, tentativo di ripristino...")
            auth.load_session(controller.context)
            page.reload()
            page.wait_for_timeout(3000)

        if not auth.is_logged_in(page):
            logger.info("Login richiesto...")

            if not auth.wait_for_login_page(page):
                logger.error("Pagina di login non trovata")
                controller.stop()
                sys.exit(1)

            email, password = get_credentials()

            if auth.perform_login(page, email, password):
                auth.save_session(controller.context)
                logger.info("Login completato e sessione salvata")
            else:
                logger.error("Login fallito")
                controller.stop()
                sys.exit(1)
        else:
            logger.info("Già loggato con sessione salvata")

        logger.info("=== Autenticazione completata ===")

        # Phase 2+: Continuous scan-relist loop
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
        with Live(
            make_status_table("In attesa...", 0, 0, 0),
            refresh_per_second=2,
            console=live_console,
        ) as live:
            while True:
                cycle += 1
                logger.info(f"=== Ciclo {cycle} ===")

                # Verifica sessione prima di ogni ciclo
                if not ensure_session(page, auth, controller, get_credentials):
                    logger.error("Sessione non valida, impossibile procedere")
                    break

                # Naviga al Transfer List
                live.update(make_status_table("Navigazione...", 0, 0, 0))
                nav_success = False
                try:
                    nav_success = navigator.go_to_transfer_list()
                except Exception as e:
                    logger.warning(f"Timeout navigazione, riprovo: {e}")
                    page.reload()
                    page.wait_for_timeout(3000)
                    try:
                        nav_success = navigator.go_to_transfer_list()
                    except Exception as e2:
                        logger.error(f"Secondo tentativo fallito: {e2}")

                if not nav_success:
                    logger.error("Impossibile raggiungere il Transfer List")
                    live.update(make_status_table("Errore", 0, 0, 0))
                    rate_limiter.wait()
                    continue

                # Scansiona listing
                live.update(make_status_table("Scansione...", 0, 0, 0))
                result = detector.scan_listings()

                if result.is_empty:
                    logger.info("Nessun listing trovato")
                    live.update(make_status_table(f"Ciclo {cycle}", 0, 0, 0))
                else:
                    logger.info(f"Scan: {result.total_count} listing (attivi={result.active_count}, scaduti={result.expired_count}, venduti={result.sold_count})")
                    live.update(make_status_table(f"Ciclo {cycle}", result.total_count, 0, 0))

                    # Rilista scaduti
                    if result.expired_count > 0:
                        logger.info(f"Rilist di {result.expired_count} listing scaduti...")
                        expired = [l for l in result.listings if l.needs_relist]
                        succeeded = 0
                        failed = 0

                        for listing in expired:
                            r = executor.relist_single(listing)
                            if r.success:
                                succeeded += 1
                                action_logger.info(
                                    "Rilist completato",
                                    extra={"action": "relist", "player_name": r.player_name, "success": True},
                                )
                            else:
                                failed += 1
                                action_logger.warning(
                                    "Rilist fallito",
                                    extra={"action": "relist", "player_name": r.player_name, "success": False, "error": r.error},
                                )
                            live.update(make_status_table(f"Ciclo {cycle} - Rilist", result.total_count, succeeded, failed))

                        total = succeeded + failed
                        action_logger.info(
                            "Batch completato",
                            extra={"action": "batch", "success": True, "total": total, "succeeded": succeeded},
                        )
                        logger.info(f"Rilist completato: {succeeded}/{total} successi")
                        live.update(make_status_table(f"Ciclo {cycle} - OK", result.total_count, succeeded, failed))
                    else:
                        logger.info("Nessun listing scaduto")
                        live.update(make_status_table(f"Ciclo {cycle}", result.total_count, 0, 0))

                # Attendi prossimo ciclo
                logger.info(f"Prossimo ciclo tra {scan_interval}s...")
                rate_limiter.wait()
                import time
                time.sleep(scan_interval)

        cm.save()

        input("\nPremi INVIO per chiudere il browser...")
        controller.stop()

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

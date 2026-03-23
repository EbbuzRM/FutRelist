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

from browser.controller import BrowserController
from browser.auth import AuthManager
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
from browser.relist import RelistExecutor
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


def load_config() -> dict:
    """DEPRECATED: Use ConfigManager.load() instead. Kept for backward compat."""
    config_path = Path(__file__).parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


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

        # Phase 2: Navigate to Transfer List and scan listings
        navigator = TransferMarketNavigator(page, config)
        detector = ListingDetector(page)

        logger.info("Navigazione verso Transfer List...")
        if navigator.go_to_transfer_list():
            logger.info("Transfer List raggiunta, scansione listing...")
            result = detector.scan_listings()

            if result.is_empty:
                logger.info("Nessun listing trovato sul Transfer List")
            else:
                logger.info(f"=== Scan completata: {result.total_count} listing trovati ===")
                logger.info(f"  Attivi: {result.active_count}")
                logger.info(f"  Scaduti: {result.expired_count}")
                logger.info(f"  Venduti: {result.sold_count}")

                if result.expired_count > 0:
                    logger.info(f"=== Rilist di {result.expired_count} listing scaduti ===")

                    executor = RelistExecutor(page, config)
                    expired = [l for l in result.listings if l.needs_relist]
                    batch_result = executor.relist_expired(expired)

                    logger.info(f"=== Rilist completato: {batch_result.succeeded}/{batch_result.total} successi ({batch_result.success_rate:.1f}%) ===")

                    # Structured action logging for each result
                    for r in batch_result.results:
                        if r.success:
                            action_logger.info(
                                "Rilist completato",
                                extra={"action": "relist", "player_name": r.player_name, "success": True},
                            )
                        else:
                            action_logger.warning(
                                "Rilist fallito",
                                extra={"action": "relist", "player_name": r.player_name, "success": False, "error": r.error},
                            )
                    action_logger.info(
                        "Batch completato",
                        extra={"action": "batch", "success": True, "total": batch_result.total, "succeeded": batch_result.succeeded},
                    )

                    if batch_result.failed > 0:
                        logger.warning(f"  {batch_result.failed} rilist falliti:")
                        for r in batch_result.results:
                            if not r.success:
                                logger.warning(f"    [{r.listing_index}] {r.player_name}: {r.error}")
                else:
                    logger.info("Nessun listing scaduto da rilistare")
        else:
            logger.error("Impossibile raggiungere il Transfer List")

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

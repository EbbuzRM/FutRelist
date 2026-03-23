"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
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


def load_config() -> dict:
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
        config = load_config()
        logger.info("Config caricata")

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
                    logger.info(f"-> {result.expired_count} listing scaduti da rilistare (Phase 3)")
                    for listing in result.listings:
                        if listing.needs_relist:
                            logger.info(f"  [{listing.index}] {listing.player_name} OVR {listing.rating} - {listing.current_price or '?'} coins")
        else:
            logger.error("Impossibile raggiungere il Transfer List")

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


if __name__ == "__main__":
    main()

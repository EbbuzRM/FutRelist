"""
Browser Controller - Wrapper Playwright per automazione FIFA 26 WebApp
"""
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserController:
    """Gestisce browser Playwright per FIFA 26 WebApp."""

    def __init__(self, config: dict):
        self.config = config
        self.playwright = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._is_running = False

    DEFAULT_PROFILE_DIR = Path("storage/browser_profile")

    def start(self, user_data_dir: str | None = None) -> Page:
        """Avvia il browser con profilo persistente.

        Usa launch_persistent_context() in modo che cookie, localStorage e
        il flag 'browser trusted' di EA vengano scritti su disco e riletti
        ad ogni avvio successivo, evitando la 2FA ripetuta.
        """
        if self._is_running:
            raise RuntimeError("Browser già avviato. Usa stop() prima di ricominciare.")

        browser_cfg = self.config.get("browser", {})
        viewport = browser_cfg.get("viewport", {"width": 1280, "height": 720})

        # Determina la cartella del profilo: quella passata o quella di default
        profile_path = Path(user_data_dir) if user_data_dir else self.DEFAULT_PROFILE_DIR
        profile_path.mkdir(parents=True, exist_ok=True)

        logger.info("Avvio Playwright...")
        self.playwright = sync_playwright().start()

        logger.info(
            f"Lancio browser con profilo persistente: {profile_path} "
            f"(headless={browser_cfg.get('headless', False)})"
        )

        # launch_persistent_context salva TUTTI i dati di sessione su disco:
        # cookie, localStorage, sessionStorage, IndexedDB, service workers.
        # EA la usa per riconoscere il dispositivo come trusted (no 2FA).
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=browser_cfg.get("headless", False),
            slow_mo=browser_cfg.get("slow_mo", 500),
            viewport={
                "width": viewport.get("width", 1280),
                "height": viewport.get("height", 720),
            },
            args=["--no-sandbox"]
        )

        # Riusa la pagina già aperta oppure ne crea una nuova
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

        self._is_running = True
        logger.info("Browser avviato con successo")
        return self.page

    def navigate_to_webapp(self) -> None:
        if not self._is_running or not self.page:
            raise RuntimeError("Browser non avviato. Usa start() prima.")

        url = self.config.get(
            "fifa_webapp_url", "https://www.ea.com/ea-sports-fc/ultimate-team/web-app/"
        )

        logger.info(f"Navigazione a: {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(3000)
        logger.info(f"Pagina caricata: {self.page.title()}")


    def stop(self) -> None:
        logger.info("Chiusura browser...")

        # Con launch_persistent_context non c'è un oggetto Browser separato:
        # chiudere il context salva il profilo su disco e termina il processo.
        try:
            if self.context:
                # Evita crash se la connessione è già chiusa (es. crash browser o Ctrl+C)
                self.context.close()
        except Exception as e:
            logger.debug(f"Errore durante la chiusura del contesto: {e}")
        finally:
            self.context = None

        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            self.playwright = None

        self.page = None
        self._is_running = False
        logger.info("Browser chiuso")

    def is_running(self) -> bool:
        return self._is_running

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

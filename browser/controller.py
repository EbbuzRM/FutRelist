"""
Browser Controller - Wrapper Playwright per automazione FIFA 26 WebApp
"""
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserController:
    """Gestisce browser Playwright per FIFA 26 WebApp."""

    def __init__(self, config: dict):
        self.config = config
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._is_running = False

    def start(self, user_data_dir: str | None = None) -> Page:
        if self._is_running:
            raise RuntimeError("Browser già avviato. Usa stop() prima di ricominciare.")

        browser_cfg = self.config.get("browser", {})
        viewport = browser_cfg.get("viewport", {"width": 1280, "height": 720})

        logger.info("Avvio Playwright...")
        self.playwright = sync_playwright().start()

        logger.info(f"Lancio browser (headless={browser_cfg.get('headless', False)})...")
        
        launch_args = []
        if user_data_dir:
            logger.info(f"Usando profilo browser esistente: {user_data_dir}")
            launch_args.append(f"--user-data-dir={user_data_dir}")

        self.browser = self.playwright.chromium.launch(
            headless=browser_cfg.get("headless", False),
            slow_mo=browser_cfg.get("slow_mo", 500),
            args=launch_args if launch_args else None,
        )

        context_args = {
            "viewport": {
                "width": viewport.get("width", 1280),
                "height": viewport.get("height", 720),
            }
        }

        # Se NON abbiamo user_data_dir, creiamo un profilo nuovo (primo avvio)
        # Se ABBIamo user_data_dir, non creiamo nuovo context (il profilo è già aperto)
        if not user_data_dir:
            logger.info("Creazione nuovo profilo browser...")
            self.context = self.browser.new_context(**context_args)
            self.page = self.context.new_page()
        else:
            # Il profilo esistente ha già una context aperta
            # Prendiamo la prima context disponibile
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            else:
                # Nessuna context, creiamo nuova
                self.context = self.browser.new_context(**context_args)
                self.page = self.context.new_page()

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
        self.page.goto(url, wait_until="networkidle", timeout=60000)
        logger.info(f"Pagina caricata: {self.page.title()}")

    def get_page(self) -> Page:
        if not self._is_running or not self.page:
            raise RuntimeError("Browser non avviato. Usa start() prima.")
        return self.page

    def stop(self) -> None:
        logger.info("Chiusura browser...")

        if self.context:
            self.context.close()
            self.context = None

        if self.browser:
            self.browser.close()
            self.browser = None

        if self.playwright:
            self.playwright.stop()
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

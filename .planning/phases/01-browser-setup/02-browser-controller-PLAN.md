---
name: "02-browser-controller"
description: "Controller Playwright per lanciare browser e navigare a FIFA 26 WebApp"
wave: 1
autonomous: true
gap_closure: false
---

## Objective
Creare il modulo browser/controller.py che gestisce lancio browser, navigazione, e interazioni base con Playwright.

## Requirements coperti
- BROWSER-01: Lanciare sessione browser automatizzata verso FIFA 26 WebApp

## Tasks

### Task 1: Crea browser/controller.py
**type:** file_write
**path:** fifa-relist/browser/controller.py
**description:** Wrapper Playwright per controllo browser

```python
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
        """
        Inizializza controller con configurazione.
        
        Args:
            config: Dict con chiavi 'browser' (headless, slow_mo, viewport)
        """
        self.config = config
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._is_running = False
    
    def start(self) -> Page:
        """
        Avvia browser Playwright e restituisce la pagina principale.
        
        Returns:
            Page: Pagina Playwright pronta all'uso
            
        Raises:
            RuntimeError: Se browser già avviato
        """
        if self._is_running:
            raise RuntimeError("Browser già avviato. Usa stop() prima di ricominciare.")
        
        browser_cfg = self.config.get("browser", {})
        
        logger.info("Avvio Playwright...")
        self.playwright = sync_playwright().start()
        
        logger.info(f"Lancio browser (headless={browser_cfg.get('headless', False)})...")
        self.browser = self.playwright.chromium.launch(
            headless=browser_cfg.get("headless", False),
            slow_mo=browser_cfg.get("slow_mo", 500)
        )
        
        logger.info("Creazione contesto browser...")
        self.context = self.browser.new_context(
            viewport={
                "width": browser_cfg.get("viewport_width", 1280),
                "height": browser_cfg.get("viewport_height", 720)
            }
        )
        
        logger.info("Creazione pagina...")
        self.page = self.context.new_page()
        self._is_running = True
        
        logger.info("Browser avviato con successo")
        return self.page
    
    def navigate_to_webapp(self) -> None:
        """
        Naviga alla FIFA 26 WebApp.
        
        Raises:
            RuntimeError: Se browser non avviato
        """
        if not self._is_running or not self.page:
            raise RuntimeError("Browser non avviato. Usa start() prima.")
        
        url = self.config.get("fifa_webapp_url", 
                              "https://www.ea.com/fifa/ultimate-team/web-app/")
        
        logger.info(f"Navigazione a: {url}")
        self.page.goto(url, wait_until="networkidle", timeout=60000)
        logger.info(f"Pagina caricata: {self.page.title()}")
    
    def get_page(self) -> Page:
        """
        Restituisce la pagina corrente.
        
        Returns:
            Page: Pagina Playwright attiva
            
        Raises:
            RuntimeError: Se browser non avviato
        """
        if not self._is_running or not self.page:
            raise RuntimeError("Browser non avviato. Usa start() prima.")
        return self.page
    
    def stop(self) -> None:
        """Chiude browser e pulisce risorse."""
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
        """Verifica se il browser è attivo."""
        return self._is_running
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
```

### Task 2: Aggiorna main.py per usare BrowserController
**type:** file_write
**path:** fifa-relist/main.py
**description:** Integra BrowserController nel main

```python
"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
import json
import logging
import sys
from pathlib import Path

from browser.controller import BrowserController

def setup_logging():
    """Configura logging con output su file e console."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "fifa-relist.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def load_config():
    """Carica configurazione da config.json."""
    config_path = Path("config/config.json")
    if not config_path.exists():
        raise FileNotFoundError(f"Config non trovato: {config_path}")
    with open(config_path) as f:
        return json.load(f)

def main():
    """Entry point principale."""
    logger = setup_logging()
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")
    
    try:
        config = load_config()
        logger.info(f"Config caricata da config/config.json")
        
        # Avvia browser
        controller = BrowserController(config)
        page = controller.start()
        
        # Naviga alla WebApp
        controller.navigate_to_webapp()
        logger.info(f"WebApp caricata: {page.title()}")
        
        # TODO: Autenticazione e gestione sessione (Plan 03)
        logger.info("In attesa di implementazione autenticazione...")
        
        # Mantieni browser aperto per debug
        input("Premi INVIO per chiudere il browser...")
        controller.stop()
        
    except Exception as e:
        logger.error(f"Errore: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Success Criteria
- [ ] browser/controller.py con classe BrowserController
- [ ] start() lancia browser Playwright
- [ ] navigate_to_webapp() naviga a FIFA 26 WebApp
- [ ] stop() chiude browser correttamente
- [ ] Context manager (__enter__/__exit__) funzionante
- [ ] main.py integrato con BrowserController
- [ ] Esecuzione test: python main.py apre browser e naviga

---
name: "03-auth-session"
description: "Autenticazione FIFA 26 e gestione sessione/cookie"
wave: 1
autonomous: true
gap_closure: false
---

## Objective
Implementare autenticazione a FIFA 26 WebApp con gestione cookie persistente tra sessioni.

## Requirements coperti
- BROWSER-02: Autenticarsi con credenziali FIFA 26 (salvate in modo sicuro)
- BROWSER-03: Mantenere cookie di sessione tra i riavvii

## Tasks

### Task 1: Crea browser/auth.py
**type:** file_write
**path:** fifa-relist/browser/auth.py
**description:** Modulo autenticazione e gestione cookie

```python
"""
Autenticazione FIFA 26 WebApp - Gestione login e sessione persistente
"""
import json
import logging
from pathlib import Path
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

# Selettori per elementi della WebApp (aggiornabili se cambiano)
SELECTORS = {
    "login_button": 'button:has-text("Accedi"), button:has-text("Login"), button:has-text("Sign In")',
    "email_input": 'input[type="email"], input[name="email"], #email',
    "password_input": 'input[type="password"], #password',
    "submit_button": 'button[type="submit"], button:has-text("Accedi"), button:has-text("Log In")',
    "main_page": '.ut-app, #MainContent, .main-content',
    "transfer_market": 'button:has-text("Transfer Market"), .icon-transfer',
    "my_listings": 'button:has-text("My Listings"), .ut-tile-transfer-list',
    "webapp_home": '.ut-app, .ea-app'
}

class AuthManager:
    """Gestisce autenticazione e sessione FIFA 26 WebApp."""
    
    def __init__(self, config: dict):
        """
        Inizializza AuthManager.
        
        Args:
            config: Configurazione con percorsi storage
        """
        self.config = config
        self.storage_dir = Path("storage")
        self.storage_dir.mkdir(exist_ok=True)
        self.cookies_file = self.storage_dir / "cookies.json"
        self.state_file = self.storage_dir / "browser_state.json"
    
    def has_saved_session(self) -> bool:
        """Verifica se esiste una sessione salvata."""
        return self.cookies_file.exists() and self.state_file.exists()
    
    def load_session(self, context) -> bool:
        """
        Carica sessione salvata nel contesto browser.
        
        Args:
            context: BrowserContext Playwright
            
        Returns:
            bool: True se caricata con successo
        """
        if not self.has_saved_session():
            logger.info("Nessuna sessione salvata trovata")
            return False
        
        try:
            # Carica stato browser (include cookies)
            with open(self.state_file) as f:
                state = json.load(f)
            
            context.storage_state = state
            logger.info("Sessione salvata caricata con successo")
            return True
            
        except Exception as e:
            logger.warning(f"Errore caricamento sessione: {e}")
            return False
    
    def save_session(self, context) -> None:
        """
        Salva sessione corrente su disco.
        
        Args:
            context: BrowserContext Playwright
        """
        try:
            state = context.storage_state()
            
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            
            # Salva anche solo i cookies per compatibilità
            cookies = state.get("cookies", [])
            with open(self.cookies_file, "w") as f:
                json.dump(cookies, f, indent=2)
            
            logger.info(f"Sessione salvata ({len(cookies)} cookies)")
            
        except Exception as e:
            logger.error(f"Errore salvataggio sessione: {e}")
    
    def is_logged_in(self, page: Page) -> bool:
        """
        Verifica se l'utente è già loggato.
        
        Args:
            page: Pagina Playwright
            
        Returns:
            bool: True se loggato (nella home WebApp)
        """
        try:
            # Cerca elementi della home WebApp
            home_element = page.query_selector(SELECTORS["webapp_home"])
            if home_element:
                logger.info("Utente già loggato (home WebApp rilevata)")
                return True
            
            # Controlla URL
            if "web-app" in page.url and "login" not in page.url.lower():
                logger.info("Utente già loggato (URL conferma)")
                return True
            
            return False
            
        except Exception:
            return False
    
    def wait_for_login_page(self, page: Page, timeout: int = 30000) -> bool:
        """
        Aspetta che la pagina di login appaia.
        
        Args:
            page: Pagina Playwright
            timeout: Timeout in ms
            
        Returns:
            bool: True se pagina di login rilevata
        """
        try:
            page.wait_for_selector(
                SELECTORS["login_button"],
                timeout=timeout
            )
            logger.info("Pagina di login rilevata")
            return True
        except Exception:
            logger.warning("Pagina di login non rilevata nel timeout")
            return False
    
    def perform_login(self, page: Page, email: str, password: str) -> bool:
        """
        Esegue login con credenziali fornite.
        
        Args:
            page: Pagina Playwright
            email: Email EA account
            password: Password EA account
            
        Returns:
            bool: True se login riuscito
        """
        try:
            logger.info("Tentativo di login...")
            
            # Clicca bottone login
            login_btn = page.query_selector(SELECTORS["login_button"])
            if login_btn:
                login_btn.click()
                page.wait_for_timeout(2000)
            
            # Inserisci email
            email_input = page.query_selector(SELECTORS["email_input"])
            if email_input:
                email_input.fill(email)
                logger.info("Email inserita")
            else:
                logger.error("Campo email non trovato")
                return False
            
            # Inserisci password
            pwd_input = page.query_selector(SELECTORS["password_input"])
            if pwd_input:
                pwd_input.fill(password)
                logger.info("Password inserita")
            else:
                logger.error("Campo password non trovato")
                return False
            
            # Clicca submit
            submit_btn = page.query_selector(SELECTORS["submit_button"])
            if submit_btn:
                submit_btn.click()
                logger.info("Submit cliccato")
            else:
                logger.error("Bottone submit non trovato")
                return False
            
            # Aspetta navigazione
            page.wait_for_timeout(5000)
            
            # Verifica login riuscito
            if self.is_logged_in(page):
                logger.info("Login riuscito!")
                return True
            
            logger.warning("Login potrebbe non essere riuscito")
            return False
            
        except Exception as e:
            logger.error(f"Errore durante login: {e}")
            return False
    
    def delete_saved_session(self) -> None:
        """Elimina sessione salvata."""
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Sessione salvata eliminata")
```

### Task 2: Aggiorna main.py per usare AuthManager
**type:** file_write
**path:** fifa-relist/main.py
**description:** Integra autenticazione nel flusso principale

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
from browser.auth import AuthManager

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

def get_credentials():
    """
    Ottieni credenziali da input utente o variabili ambiente.
    
    Returns:
        tuple: (email, password)
    """
    import os
    
    # Prima prova variabili ambiente
    email = os.environ.get("FIFA_EMAIL")
    password = os.environ.get("FIFA_PASSWORD")
    
    if email and password:
        return email, password
    
    # Altrimenti chiedi input
    print("\n=== Credenziali FIFA 26 ===")
    email = input("Email EA: ").strip()
    password = input("Password EA: ").strip()
    
    return email, password

def main():
    """Entry point principale."""
    logger = setup_logging()
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")
    
    try:
        config = load_config()
        logger.info("Config caricata")
        
        # Inizializza componenti
        controller = BrowserController(config)
        auth = AuthManager(config)
        
        # Avvia browser
        page = controller.start()
        
        # Naviga alla WebApp
        controller.navigate_to_webapp()
        logger.info(f"WebApp caricata: {page.title()}")
        
        # Gestisci autenticazione
        if auth.has_saved_session():
            logger.info("Sessione salvata trovata, tentativo di ripristino...")
            # Il context ha già i cookie dal storage_state
            page.reload()
            page.wait_for_timeout(3000)
        
        if not auth.is_logged_in(page):
            logger.info("Login richiesto...")
            
            # Aspetta pagina di login
            if not auth.wait_for_login_page(page):
                logger.error("Pagina di login non trovata")
                controller.stop()
                sys.exit(1)
            
            # Ottieni credenziali
            email, password = get_credentials()
            
            # Esegui login
            if auth.perform_login(page, email, password):
                # Salva sessione per prossima volta
                auth.save_session(controller.context)
                logger.info("Login completato e sessione salvata")
            else:
                logger.error("Login fallito")
                controller.stop()
                sys.exit(1)
        else:
            logger.info("Già loggato con sessione salvata")
        
        logger.info("=== Autenticazione completata ===")
        logger.info("Browser pronto per operazioni (rilisting, ecc.)")
        
        # Mantieni browser aperto per debug
        input("\nPremi INVIO per chiudere il browser...")
        controller.stop()
        
    except KeyboardInterrupt:
        logger.info("Interruzione utente")
        if 'controller' in locals():
            controller.stop()
    except Exception as e:
        logger.error(f"Errore: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Task 3: Aggiorna config.json con opzioni auth
**type:** file_write
**path:** fifa-relist/config/config.json
**description:** Aggiunge sezione auth alla config

```json
{
  "fifa_webapp_url": "https://www.ea.com/fifa/ultimate-team/web-app/",
  "browser": {
    "headless": false,
    "slow_mo": 500,
    "viewport_width": 1280,
    "viewport_height": 720
  },
  "auth": {
    "save_session": true,
    "session_timeout_hours": 24,
    "use_env_credentials": true
  },
  "scan_interval_seconds": 60,
  "listing_defaults": {
    "duration": "3h",
    "price_adjustment_type": "percentage",
    "price_adjustment_value": 0
  },
  "rate_limiting": {
    "min_delay_ms": 2000,
    "max_delay_ms": 5000
  }
}
```

## Success Criteria
- [ ] browser/auth.py con classe AuthManager
- [ ] has_saved_session() rileva sessioni salvate
- [ ] load_session()/save_session() gestiscono cookie su JSON
- [ ] is_logged_in() rileva stato login
- [ ] perform_login() esegue login con credenziali
- [ ] main.py integra AuthManager
- [ ] Login funziona con credenziali reali (test manuale)
- [ ] Sessione persiste tra riavvii (cookie salvati)
- [ ] Variabili ambiente FIFA_EMAIL/FIFA_PASSWORD supportate

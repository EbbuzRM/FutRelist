"""
Autenticazione FIFA 26 WebApp - Gestione login e sessione persistente
"""
import json
import logging
from pathlib import Path
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Autenticazione fallita. Il chiamante decide se terminare o recuperare."""

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
        self.config = config
        self.storage_dir = Path("storage")
        self.storage_dir.mkdir(exist_ok=True)
        self.cookies_file = self.storage_dir / "cookies.json"
        self.state_file = self.storage_dir / "browser_state.json"
    
    def has_saved_session(self) -> bool:
        return self.cookies_file.exists() and self.state_file.exists()
    
    def load_session(self, context) -> bool:
        if not self.has_saved_session():
            logger.info("Nessuna sessione salvata trovata")
            return False
        
        try:
            with open(self.state_file) as f:
                state = json.load(f)
            
            context.add_cookies(state.get("cookies", []))
            logger.info("Sessione salvata caricata con successo")
            return True
            
        except Exception as e:
            logger.warning(f"Errore caricamento sessione: {e}")
            return False
    
    def save_session(self, context) -> None:
        try:
            state = context.storage_state()
            
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            
            cookies = state.get("cookies", [])
            with open(self.cookies_file, "w") as f:
                json.dump(cookies, f, indent=2)
            
            logger.info(f"Sessione salvata ({len(cookies)} cookies)")
            
        except Exception as e:
            logger.error(f"Errore salvataggio sessione: {e}")
    
    def is_logged_in(self, page: Page) -> bool:
        try:
            home_element = page.query_selector(SELECTORS["webapp_home"])
            if home_element:
                logger.info("Utente già loggato (home WebApp rilevata)")
                return True
            
            if "web-app" in page.url and "login" not in page.url.lower():
                logger.info("Utente già loggato (URL conferma)")
                return True
            
            return False
            
        except Exception:
            return False
    
    def wait_for_login_page(self, page: Page, timeout: int = 30000) -> bool:
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
        try:
            logger.info("Tentativo di login...")
            
            login_btn = page.query_selector(SELECTORS["login_button"])
            if login_btn:
                login_btn.click()
                page.wait_for_timeout(2000)
            
            email_input = page.query_selector(SELECTORS["email_input"])
            if email_input:
                email_input.fill(email)
                logger.info("Email inserita")
            else:
                logger.error("Campo email non trovato")
                return False
            
            pwd_input = page.query_selector(SELECTORS["password_input"])
            if pwd_input:
                pwd_input.fill(password)
                logger.info("Password inserita")
            else:
                logger.error("Campo password non trovato")
                return False
            
            submit_btn = page.query_selector(SELECTORS["submit_button"])
            if submit_btn:
                submit_btn.click()
                logger.info("Submit cliccato")
            else:
                logger.error("Bottone submit non trovato")
                return False
            
            page.wait_for_timeout(5000)
            
            if self.is_logged_in(page):
                logger.info("Login riuscito!")
                return True
            
            logger.warning("Login potrebbe non essere riuscito")
            return False
            
        except Exception as e:
            logger.error(f"Errore durante login: {e}")
            return False
    
    def delete_saved_session(self) -> None:
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Sessione salvata eliminata")

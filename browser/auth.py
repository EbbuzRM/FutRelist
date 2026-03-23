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
    "login_button": 'button:has-text("Login")',
    "email_input": 'input[placeholder*="phone or email"], input[placeholder*="email"]',
    "next_button": 'button:has-text("NEXT")',
    "password_input": 'input[placeholder*="password"]',
    "submit_button": 'button:has-text("Sign in")',
    "verification_code_input": '#twoFactorCode, input[name="twoFactorCode"]',
    "verification_submit": '#btnSubmit, button:has-text("Submit")',
    "webapp_home": '.ut-app, .ea-app',
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
            # Check URL — se non siamo più sulla pagina di login, siamo dentro
            url = page.url.lower()
            if "web-app" in url and "login" not in url:
                return True

            # Check elementi DOM
            home_element = page.query_selector(SELECTORS["webapp_home"])
            if home_element:
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
        """Esegue il login EA in due step: email → NEXT → password → Sign in.

        Il login avviene su signin.ea.com (redirect completo dalla WebApp).
        """
        try:
            logger.info("Tentativo di login...")

            # Se siamo sulla WebApp, clicca "Login" per andare alla pagina signin
            login_btn = page.query_selector(SELECTORS["login_button"])
            if login_btn:
                login_btn.click()
                logger.info("Pulsante Login cliccato, attesa redirect a signin.ea.com...")
                # Attendi navigazione alla pagina di login
                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

            # Step 1: Inserisci email (campo su signin.ea.com)
            email_input = page.wait_for_selector(
                SELECTORS["email_input"], state="visible", timeout=15000
            )
            if not email_input:
                logger.error("Campo email non trovato")
                return False

            email_input.fill(email)
            logger.info("Email inserita")

            # Step 2: Clicca "NEXT"
            page.wait_for_timeout(1000)
            next_btn = page.query_selector(SELECTORS["next_button"])
            if next_btn:
                next_btn.click()
                logger.info("NEXT cliccato")
                page.wait_for_timeout(3000)
            else:
                logger.error("Bottone NEXT non trovato")
                return False

            # Step 3: Inserisci password (appare dopo NEXT)
            pwd_input = page.wait_for_selector(
                SELECTORS["password_input"], state="visible", timeout=10000
            )
            if not pwd_input:
                logger.error("Campo password non trovato dopo NEXT")
                return False

            pwd_input.fill(password)
            logger.info("Password inserita")

            # Step 4: Clicca "Sign in"
            submit_btn = page.query_selector(SELECTORS["submit_button"])
            if submit_btn:
                submit_btn.click()
                logger.info("Sign in cliccato")
            else:
                logger.error("Bottone Sign in non trovato")
                return False

            # Attendi redirect da signin.ea.com → WebApp
            logger.info("Attesa redirect a WebApp...")
            page.wait_for_timeout(5000)

            # Gestione eventuale 2FA EA
            if not self.handle_verification_if_needed(page):
                logger.error("Verifica 2FA fallita o interrotta")
                return False

            # Attendi caricamento WebApp fino a 30s
            logger.info("Attesa caricamento WebApp...")
            for i in range(30):
                if self.is_logged_in(page):
                    logger.info("Login riuscito!")
                    return True
                page.wait_for_timeout(1000)
                if i % 10 == 0 and i > 0:
                    logger.info(f"  ...ancora in attesa ({i}s)")

            logger.warning("Login fallito — WebApp non rilevata dopo 30s")
            return False

        except Exception as e:
            logger.error(f"Errore durante login: {e}")
            return False

    def handle_verification_if_needed(self, page: Page) -> bool:
        """Gestisce il 2FA/verifica identità EA se richiesto.

        Ritorna True se la verifica è passata o non necessaria, False se fallita.
        """
        # Check se appare il campo codice verifica
        code_input = page.query_selector(SELECTORS["verification_code_input"])

        if not code_input:
            return True

        logger.info("==================================================")
        logger.info("VERIFICA 2FA — Inserisci il codice NEL BROWSER.")
        logger.info("Lo script attende max 2 minuti...")
        logger.info("==================================================")

        try:
            # Polling: ogni 2s controlla se siamo nell'app
            for _ in range(60):
                page.wait_for_timeout(2000)
                if self.is_logged_in(page):
                    logger.info("Verifica completata!")
                    return True
                # Se il campo codice è scomparso, probabilmente siamo dentro
                if not page.query_selector(SELECTORS["verification_code_input"]):
                    page.wait_for_timeout(2000)
                    if self.is_logged_in(page):
                        logger.info("Verifica completata (campo codice scomparso)!")
                        return True
                    break
        except Exception:
            pass

        logger.error("Timeout verifica 2FA")
        return False

        # Se c'è il pulsante "Send Code", cliccalo
        if send_code_btn:
            logger.info("Verifica identità EA — invio codice...")
            send_code_btn.click()
            page.wait_for_timeout(2000)
            code_input = page.query_selector(SELECTORS["verification_code_input"])

        if code_input:
            logger.info("==================================================")
            logger.info("VERIFICA 2FA — Inserisci il codice NEL BROWSER.")
            logger.info("Lo script attende max 2 minuti...")
            logger.info("==================================================")

            try:
                # Polling: ogni 2s controlla se siamo nell'app
                for _ in range(60):
                    page.wait_for_timeout(2000)
                    if self.is_logged_in(page):
                        logger.info("Verifica completata!")
                        return True
                    # Se il campo codice è scomparso, probabilmente siamo dentro
                    if not page.query_selector(SELECTORS["verification_code_input"]):
                        page.wait_for_timeout(2000)
                        if self.is_logged_in(page):
                            logger.info("Verifica completata (campo codice scomparso)!")
                            return True
                        break
            except Exception:
                pass

            logger.error("Timeout verifica 2FA")
            return False

        return True
    
    def delete_saved_session(self) -> None:
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Sessione salvata eliminata")

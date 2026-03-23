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
    "verification_send_code": 'button:has-text("Send Code")',
    "verification_code_input": 'input[placeholder*="digit code"], input[placeholder*="verification"]',
    "verification_submit": 'button:has-text("Sign in")',
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
            url = page.url.lower()
            # Se siamo su signin.ea.com, non siamo loggati
            if "signin.ea.com" in url:
                return False
            # Se siamo sulla WebApp, siamo loggati
            if "web-app" in url:
                return True
            return False
        except Exception:
            return False
    
    def wait_for_login_page(self, page: Page, timeout: int = 30000) -> bool:
        try:
            login_btn = page.get_by_role("button", name="Login")
            login_btn.first.wait_for(state="visible", timeout=timeout)
            logger.info("Pagina di login rilevata")
            return True
        except Exception:
            logger.warning("Pagina di login non rilevata nel timeout")
            return False
    
    def perform_login(self, page: Page, email: str, password: str) -> bool:
        """Esegue il login EA in due step: email → NEXT → password → Sign in.

        Il login avviene su signin.ea.com (redirect completo dalla WebApp).
        Usa get_by_role per compatibilità con la WebApp React.
        """
        try:
            logger.info("Tentativo di login...")

            # Se siamo sulla WebApp, clicca "Login" per andare alla pagina signin
            login_btn = page.get_by_role("button", name="Login")
            if login_btn.count():
                login_btn.first.click()
                logger.info("Pulsante Login cliccato, attesa redirect a signin.ea.com...")
                # Attendi navigazione alla pagina signin
                try:
                    page.wait_for_url("**/signin.ea.com/**", timeout=15000)
                except Exception:
                    page.wait_for_timeout(5000)
                page.wait_for_timeout(2000)

            # Step 1: Inserisci email (campo su signin.ea.com)
            email_input = page.get_by_role("textbox", name="Phone or Email")
            if not email_input.count():
                logger.error("Campo email non trovato")
                return False

            email_input.first.fill(email)
            logger.info("Email inserita")

            # Step 2: Clicca "NEXT"
            page.wait_for_timeout(1000)
            next_btn = page.get_by_role("button", name="NEXT")
            if not next_btn.count():
                logger.error("Bottone NEXT non trovato")
                return False

            next_btn.first.click()
            logger.info("NEXT cliccato")
            page.wait_for_timeout(3000)

            # Step 3: Inserisci password (appare dopo NEXT)
            pwd_input = page.get_by_role("textbox", name="Password")
            if not pwd_input.count():
                logger.error("Campo password non trovato dopo NEXT")
                return False

            pwd_input.first.fill(password)
            logger.info("Password inserita")

            # Step 4: Clicca "Sign in"
            sign_in_btn = page.get_by_role("button", name="Sign in")
            if not sign_in_btn.count():
                logger.error("Bottone Sign in non trovato")
                return False

            sign_in_btn.first.click()
            logger.info("Sign in cliccato")

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
        """Gestisce il 2FA/verifica identità EA se richiesto."""
        # Check se appare il pulsante "Send Code"
        send_code_btn = page.get_by_role("button", name="Send Code")
        if send_code_btn.count():
            logger.info("2FA richiesto — invio codice via email...")
            send_code_btn.first.click()
            page.wait_for_timeout(3000)

        # Check se appare il campo codice
        code_input = page.get_by_role("textbox", name="Code")
        if not code_input.count():
            code_input = page.get_by_placeholder("Enter 6 digit code")
        if not code_input.count():
            return True

        logger.info("==================================================")
        logger.info("VERIFICA 2FA — Controlla la tua email per il codice.")
        logger.info("Inseriscilo NEL BROWSER aperto.")
        logger.info("Lo script attende max 2 minuti...")
        logger.info("==================================================")

        try:
            for _ in range(60):
                page.wait_for_timeout(2000)
                if self.is_logged_in(page):
                    logger.info("Verifica completata!")
                    return True
                # Se il campo codice è scomparso, probabilmente siamo dentro
                if not page.get_by_role("textbox", name="Code").count():
                    page.wait_for_timeout(2000)
                    if self.is_logged_in(page):
                        logger.info("Verifica completata!")
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

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
    "next_button": '#logInBtn, button:has-text("Next"), button:has-text("Avanti"), button:has-text("next")',
    "password_input": 'input[type="password"], #password',
    "submit_button": 'button[type="submit"], button:has-text("Accedi"), button:has-text("Log In")',
    "verification_send_code": '#btnSendCode, button:has-text("Send Code"), button:has-text("Invia codice")',
    "verification_code_input": '#twoFactorCode, input[name="twoFactorCode"], #verificationCode',
    "verification_submit": '#btnSubmit, button:has-text("Submit"), button:has-text("Verifica")',
    "verification_error": '#origin-tfa-container .general-error, .error-message',
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
        """Esegue il login EA in due step: email → Next → password → Log In."""
        try:
            logger.info("Tentativo di login...")

            # Clicca il pulsante login se presente (dalla home WebApp)
            login_btn = page.query_selector(SELECTORS["login_button"])
            if login_btn:
                login_btn.click()
                page.wait_for_timeout(2000)

            # Step 1: Inserisci email
            email_input = page.query_selector(SELECTORS["email_input"])
            if not email_input:
                logger.error("Campo email non trovato")
                return False

            email_input.fill(email)
            logger.info("Email inserita")

            # Step 2: Clicca "Next" / "Avanti" per mostrare il campo password
            page.wait_for_timeout(1000)
            next_btn = page.query_selector(SELECTORS["next_button"])
            if next_btn:
                next_btn.click()
                logger.info("Bottone Next/Avanti cliccato")
                page.wait_for_timeout(3000)
            else:
                logger.warning("Bottone Next non trovato, provo comunque...")

            # Step 3: Inserisci password (appare dopo il click su Next)
            pwd_input = page.wait_for_selector(
                SELECTORS["password_input"], state="visible", timeout=10000
            )
            if not pwd_input:
                logger.error("Campo password non trovato dopo Next")
                return False

            pwd_input.fill(password)
            logger.info("Password inserita")

            # Step 4: Clicca submit / Log In
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

    def handle_verification_if_needed(self, page: Page) -> bool:
        """Gestisce il 2FA/verifica identità EA se richiesto.

        Ritorna True se la verifica è passata o non necessaria, False se fallita.
        """
        # Check se appare il pulsante "Send Code" (prima attivazione 2FA)
        send_code_btn = page.query_selector(SELECTORS["verification_send_code"])
        if send_code_btn:
            logger.info("Verifica identità EA richiesta (prima attivazione)")
            send_code_btn.click()
            page.wait_for_timeout(2000)

        # Check se appare il campo codice verifica
        code_input = page.query_selector(SELECTORS["verification_code_input"])
        if not code_input:
            return True

        logger.info("Verifica identità EA richiesta — inserisci il codice ricevuto")

        for attempt in range(3):
            code = input(f"Codice verifica (tentativo {attempt + 1}/3): ").strip()
            if not code:
                logger.warning("Codice vuoto, riprova")
                continue

            code_input = page.query_selector(SELECTORS["verification_code_input"])
            if not code_input:
                logger.error("Campo codice scomparso")
                return False

            code_input.fill(code)

            submit_btn = page.query_selector(SELECTORS["verification_submit"])
            if submit_btn:
                submit_btn.click()
                page.wait_for_timeout(3000)

            # Check se il codice era errato
            error_el = page.query_selector(SELECTORS["verification_error"])
            if error_el:
                error_text = error_el.inner_text()
                logger.warning(f"Codice errato: {error_text}")
                continue

            # Check se siamo loggati
            if self.is_logged_in(page):
                logger.info("Verifica completata con successo!")
                return True

            # Il campo codice potrebbe essere ancora visibile (altro errore)
            code_input = page.query_selector(SELECTORS["verification_code_input"])
            if code_input:
                logger.warning("Codice non accettato, riprova")
                continue

            # Campo scomparso ma non loggati — stato sconosciuto
            logger.warning("Stato verifica incerto")
            return True

        logger.error("Verifica fallita dopo 3 tentativi")
        return False
    
    def delete_saved_session(self) -> None:
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Sessione salvata eliminata")

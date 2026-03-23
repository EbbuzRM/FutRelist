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
    "submit_button": '#logInBtn, button[type="submit"], button:has-text("Accedi"), button:has-text("Log In"), button:has-text("Sign In")',
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
            # Check URL — se non siamo più sulla pagina di login, siamo dentro
            url = page.url.lower()
            if "web-app" in url and "login" not in url:
                logger.info("Utente loggato (URL conferma)")
                return True

            # Check elementi DOM
            home_element = page.query_selector(SELECTORS["webapp_home"])
            if home_element:
                logger.info("Utente loggato (WebApp rilevata)")
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
            # Proviamo più selettori e logghiamo cosa troviamo
            login_selectors = [
                'button:has-text("Accedi")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'a:has-text("Accedi")',
                'a:has-text("Login")',
                'a:has-text("Sign In")',
            ]

            login_btn = None
            for sel in login_selectors:
                login_btn = page.query_selector(sel)
                if login_btn:
                    logger.info(f"Login button trovato con: {sel}")
                    break

            if login_btn:
                # Assicuriamoci che il bottone sia visibile e cliccabile
                try:
                    login_btn.scroll_into_view_if_needed()
                except Exception:
                    pass
                login_btn.click()
                logger.info("Pulsante Login iniziale cliccato")

                # Attendi che appaia email o WebApp (login automatico)
                try:
                    page.wait_for_selector(
                        f'{SELECTORS["webapp_home"]}, {SELECTORS["email_input"]}',
                        timeout=15000,
                    )
                except Exception:
                    logger.warning("Timeout attesa post-click login")

                if self.is_logged_in(page):
                    logger.info("Login automatico effettuato!")
                    return True
            else:
                logger.info("Nessun bottone login trovato, cerco campo email diretto...")

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

            # Attendi redirect post-login (può essere lento)
            logger.info("Attesa redirect post-login...")
            page.wait_for_timeout(5000)

            # Gestione eventuale 2FA EA
            if not self.handle_verification_if_needed(page):
                logger.error("Verifica 2FA fallita o interrotta")
                return False

            # Attendi caricamento WebApp fino a 30s
            logger.info("Attesa caricamento WebApp...")
            for _ in range(30):
                if self.is_logged_in(page):
                    logger.info("Login riuscito!")
                    return True
                page.wait_for_timeout(1000)

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
        send_code_btn = page.query_selector(SELECTORS["verification_send_code"])

        if not code_input and not send_code_btn:
            return True

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

"""
Autenticazione FIFA 26 WebApp - Gestione login e sessione persistente
"""
import json
import logging
import shutil
import time
from pathlib import Path
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Autenticazione fallita. Il chiamante decide se terminare o recuperare."""

SELECTORS = {
    # Selettore per il messaggio di sessione console attiva
    "console_error": '.ut-messaging-view, .dialog-body, .dialog-title',
    # Dialog messaggi generici / errori
    "generic_dialog": '.dialog-body, .ut-messaging-view',
}


class AuthManager:
    """Gestisce autenticazione e sessione FIFA 26 WebApp."""

    PROFILE_DIR = Path("storage/browser_profile")

    def __init__(self, config: dict):
        self.config = config
        self.PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    def has_saved_session(self) -> bool:
        """True se esiste un profilo browser salvato."""
        return self.PROFILE_DIR.exists() and any(self.PROFILE_DIR.iterdir())

    def load_session(self) -> str | None:
        """Ritorna il percorso del profilo se esiste."""
        if self.has_saved_session():
            return str(self.PROFILE_DIR)
        return None

    def delete_saved_session(self) -> None:
        """Cancella il profilo browser."""
        if self.PROFILE_DIR.exists():
            shutil.rmtree(self.PROFILE_DIR)
            logger.info("Profilo browser cancellato")

    def save_session(self, context) -> None:
        """Forza il flush della sessione su disco.

        Con launch_persistent_context Playwright salva automaticamente tutti i dati
        (cookie, localStorage, IndexedDB) nel PROFILE_DIR alla chiusura. Questo metodo
        è un no-op esplicito che documenta l'intenzione: la persistenza è gestita dal
        profilo, non da file JSON separati.
        """
        try:
            state = context.storage_state()
            cookies = state.get("cookies", [])
            logger.info(f"Sessione attiva con {len(cookies)} cookies (persistita via profilo browser)")
        except Exception as e:
            logger.debug(f"Impossibile leggere storage_state (non critico): {e}")

    def check_and_handle_disconnect_modal(self, page: Page) -> bool:
        """Controlla se c'è il popup 'Cannot Authenticate' / 'Impossibile autenticare'.
        Clicca 'Ok' se lo trova e aspetta il logout.
        
        Ritorna True se ha trovato e gestito il modale.
        """
        try:
            # Parole chiave del modale di disconnessione
            disconnect_keywords = [
                "cannot authenticate",
                "unable to authenticate with the football",
                "logged out of the application",
                "impossibile autenticare",
                "sarai disconnesso dall'applicazione"
            ]
            
            dialogs = page.query_selector_all(SELECTORS["generic_dialog"])
            for dialog in dialogs:
                if dialog and dialog.is_visible():
                    text = dialog.text_content().lower()
                    if any(kw in text for kw in disconnect_keywords):
                        logger.warning("Rilevato modale ERROR/DISCONNECT ('Cannot Authenticate'). Clicco OK...")
                        # Cerca il pulsante Ok / OK
                        ok_btn = dialog.query_selector('button:has-text("Ok"), button:has-text("OK")')
                        if ok_btn:
                            ok_btn.click(timeout=3000)
                        else:
                            # Fallback Playwright
                            page.get_by_role("button", name=re.compile("ok", re.IGNORECASE)).first.click(timeout=3000)
                            
                        logger.info("Modale disconnessione accettato. Attesa redirect a login...")
                        page.wait_for_timeout(3000)
                        return True
            return False
        except Exception as e:
            logger.debug(f"Errore durante check_and_handle_disconnect_modal: {e}")
            return False

    def is_logged_in(self, page: Page, timeout_ms: int = 15000) -> bool:
        """Verifica se l'utente è correttamente loggato nella WebApp.
        Controlla diversi elementi della UI con polling per dare tempo al caricamento.
        """
        try:
            url = page.url.lower()
            if "signin.ea.com" in url:
                return False

            # Attendiamo che lo "shield" di caricamento scompaia
            try:
                page.wait_for_selector(".ut-click-shield", state="hidden", timeout=5000)
            except Exception:
                pass

            # Indicatori di login (inglese e italiano)
            logged_in_indicators = [
                'button:has-text("Home")',
                'button:has-text("Transfers")',
                'button:has-text("Trasferimenti")',
                'button:has-text("Club")',
                '.ut-navigation-container',
                '.ut-tab-bar'
            ]

            start_time = time.time()
            while (time.time() - start_time) * 1000 < timeout_ms:
                for selector in logged_in_indicators:
                    try:
                        el = page.query_selector(selector)
                        if el and el.is_visible():
                            logger.info(f"Sessione rilevata tramite: {selector}")
                            return True
                    except Exception:
                        continue
                page.wait_for_timeout(1000)

            return False
        except Exception as e:
            logger.debug(f"Errore durante is_logged_in: {e}")
            return False

    def is_console_session_active(self, page: Page) -> bool:
        """Controlla se appare il messaggio 'Signed Into Another Device' o simili.

        La pagina EA può comparire come full-page view (non un dialog),
        quindi usiamo più metodi in cascata per essere a prova di bomba.
        """
        try:
            console_keywords = [
                "signed into another device",
                "logged in on another device",
                "cannot use the fc companion",
                "sessione già attiva",
                "altro dispositivo",
                "connessione a un altro dispositivo",
                "connected to the servers",
                "sign out from your football ultimate team",
            ]

            # 1) Segnale più affidabile: il bottone "Retry" appare SOLO su questa pagina.
            #    Usiamo get_by_role che è robusto a cambi di classe CSS EA.
            try:
                retry_btn = page.get_by_role("button", name="Retry")
                if retry_btn.count() and retry_btn.first.is_visible():
                    logger.warning("Sessione console rilevata: bottone 'Retry' visibile")
                    return True
            except Exception:
                pass

            # 2) Selettore specifico EA su dialog/view (funziona quando è un overlay)
            error_el = page.query_selector(SELECTORS["console_error"])
            if error_el and error_el.is_visible():
                text = error_el.text_content().lower()
                if any(kw in text for kw in console_keywords):
                    logger.warning(f"Sessione console rilevata (selettore): '{text.strip()[:80]}'")
                    return True

            # 3) Fallback sul testo dell'intera pagina: cattura la full-page view EA
            #    che non usa classi dialog/modal ma è comunque visibile come pagina.
            try:
                body_text = page.locator("body").inner_text(timeout=3000).lower()
                if any(kw in body_text for kw in console_keywords):
                    logger.warning("Sessione console rilevata (body text match)")
                    return True
            except Exception:
                pass

            return False
        except Exception:
            return False

    def wait_for_login_page(self, page: Page, timeout: int = 30000) -> bool:
        """Aspetta che appaia la landing page con il tasto Login o la pagina EA."""
        try:
            if "signin.ea.com" in page.url:
                logger.info("Già sulla pagina di login di EA")
                return True

            login_btn = page.get_by_role("button", name="Login")
            login_btn.first.wait_for(state="visible", timeout=timeout)
            logger.info("Pagina di login rilevata")
            return True
        except Exception:
            if "signin.ea.com" in page.url:
                return True
            try:
                logger.debug(f"URL al timeout: {page.url}")
            except Exception:
                pass
            logger.warning("Pagina di login non rilevata nel timeout")
            return False

    def perform_login(self, page: Page, email: str, password: str) -> bool:
        """Esegue il login EA in due step: email → NEXT → password → Sign in."""
        try:
            logger.info("Tentativo di login...")

            # 0) Verifica immediata: siamo già loggati?
            if self.is_logged_in(page, timeout_ms=5000):
                logger.info("Già loggato — skip login.")
                return True

            # 1) Attendi che lo shield di caricamento scompaia
            try:
                page.wait_for_selector(".ut-click-shield", state="hidden", timeout=10000)
                logger.info("Shield di caricamento scomparso")
            except Exception:
                logger.debug("Shield ancora presente o non trovato, procedo comunque")

            login_btn = page.get_by_role("button", name="Login")
            if login_btn.count():
                for attempt in range(1, 4):
                    logger.info(f"Pulsante Login trovato (tentativo {attempt}). Click per procedere...")
                    try:
                        # Prova click normale
                        login_btn.first.click(timeout=10000)
                    except Exception as e:
                        logger.warning(f"Click normale fallito (tentativo {attempt}): {e}")
                        # Fallback: click via JavaScript
                        try:
                            page.evaluate("document.querySelector('.btn-standard.primary')?.click()")
                            logger.info("Click via JavaScript eseguito")
                        except Exception as e2:
                            logger.warning(f"Anche click JS fallito: {e2}")
                            if attempt < 3:
                                page.wait_for_timeout(2000)
                                continue
                            else:
                                logger.error("Impossibile cliccare Login dopo 3 tentativi")
                                return False

                    page.wait_for_timeout(4000)

                    curr_url = page.url.lower()
                    if "signin.ea.com" in curr_url:
                        logger.info("Redirect a signin.ea.com avvenuto con successo.")
                        break

                    if self.is_logged_in(page, timeout_ms=3000):
                        logger.info("Siamo già loggati dopo il click.")
                        return True

                    if attempt < 3:
                        logger.warning(f"Click su Login ignorato o fallito (siamo ancora su {curr_url}), riprovo...")
                    else:
                        logger.error("Impossibile procedere oltre la landing page dopo 3 tentativi di click.")
                        return False

                page.wait_for_timeout(2000)

            if self.is_console_session_active(page):
                logger.warning("Sessione console attiva rilevata dopo aver cliccato Login!")
                return False

            if self.is_logged_in(page, timeout_ms=3000):
                logger.info("Login istantaneo (già autorizzato).")
                return True

            # Step 1: Email
            email_input = page.get_by_role("textbox", name="Phone or Email")
            if not email_input.count():
                logger.error("Campo email non trovato")
                return False
            email_input.first.fill(email)
            logger.info("Email inserita")

            # Step 2: NEXT
            page.wait_for_timeout(1000)
            next_btn = page.get_by_role("button", name="NEXT")
            if not next_btn.count():
                logger.error("Bottone NEXT non trovato")
                return False
            next_btn.first.click()
            logger.info("NEXT cliccato")
            page.wait_for_timeout(3000)

            # Step 3: Password
            pwd_input = page.get_by_role("textbox", name="Password")
            if not pwd_input.count():
                logger.error("Campo password non trovato dopo NEXT")
                return False
            pwd_input.first.fill(password)
            logger.info("Password inserita")

            # Step 4: Sign in
            sign_in_btn = page.get_by_role("button", name="Sign in")
            if not sign_in_btn.count():
                logger.error("Bottone Sign in non trovato")
                return False
            sign_in_btn.first.click()
            logger.info("Sign in cliccato")

            logger.info("Attesa redirect a WebApp...")
            page.wait_for_timeout(5000)

            if not self.handle_verification_if_needed(page):
                logger.error("Verifica 2FA fallita o interrotta")
                return False

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
        send_code_btn = page.get_by_role("button", name="Send Code")
        if send_code_btn.count():
            logger.info("2FA richiesto — invio codice via email...")
            send_code_btn.first.click()
            page.wait_for_timeout(3000)

        code_input = page.get_by_role("textbox", name="Code")
        if not code_input.count():
            code_input = page.get_by_placeholder("Enter 6 digit code")
        if not code_input.count():
            return True

        logger.info("==================================================")
        logger.info("VERIFICA 2FA RICHIESTA - Inserisci il codice nel browser")
        logger.info("e clicca 'Sign in'. Il bot attenderà il completamento...")
        logger.info("==================================================")

        max_wait = 120
        waited = 0
        while waited < max_wait:
            if self.is_logged_in(page):
                logger.info("Verifica completata con successo!")
                return True
            page.wait_for_timeout(2000)
            waited += 2
            if waited % 10 == 0:
                logger.info(f"In attesa del login... ({waited}/{max_wait}s)")

        logger.error("Timeout: login non completato entro 2 minuti")
        return False

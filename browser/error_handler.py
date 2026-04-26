"""Error handler with session recovery, retry, and element fallback.

Provides session expiry detection, automatic re-authentication,
retry on timeout decorator, and element-not-found handling.
"""
from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from playwright.sync_api import Error as PlaywrightError
    from browser.auth import AuthManager

logger = logging.getLogger(__name__)


def retry_on_timeout(func: Callable | None = None, *, max_retries: int = 3) -> Callable:
    """Decorator: retry a function up to max_retries times on Playwright timeout errors.

    Uses exponential backoff (1s, 2s, 4s) between retries.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from playwright.sync_api import Error as PlaywrightError
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except PlaywrightError as e:
                    last_exc = e
                    if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        logger.warning(
                            f"Timeout al tentativo {attempt + 1}/{max_retries}, "
                            f"attesa {wait}s prima del retry: {e}"
                        )
                        import time
                        time.sleep(wait)
                    else:
                        raise
            raise last_exc  # type: ignore[misc]
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def handle_element_not_found(
    page: "Page",
    selector: str,
    *,
    fallback_reload: bool = True,
) -> bool:
    """Gestisce il caso in cui un elemento non viene trovato nel DOM.

    Se fallback_reload è True, ricarica la pagina e riprova.
    Ritorna True se l'elemento è stato trovato (eventualmente dopo reload).
    """
    element = page.query_selector(selector)
    if element:
        return True

    if not fallback_reload:
        logger.warning(f"Elemento non trovato: {selector} (nessun reload)")
        return False

    logger.warning(f"Elemento non trovato: {selector}, tentativo di reload...")
    page.reload()
    page.wait_for_timeout(3000)

    element = page.query_selector(selector)
    if element:
        logger.info(f"Elemento trovato dopo reload: {selector}")
        return True

    logger.error(f"Elemento ancora non trovato dopo reload: {selector}")
    return False


def is_session_expired(page: "Page") -> bool:
    """Verifica se la sessione è scaduta controllando lo stato della pagina.

    Ritorna True se siamo chiaramente su una pagina di login/url sconosciuto.
    Ritorna False se siamo sulla WebApp (anche se non ancora del tutto caricata).
    """
    url = page.url.lower()
    if "signin.ea.com" in url or "login" in url:
        logger.info(f"Sessione scaduta: rilevata URL di login ({url})")
        return True

    if "web-app" in url:
        # Siamo sulla webapp: non è scaduta anche se gli elementi non sono
        # ancora visibili (potrebbe essere in caricamento).
        return False

    logger.info("Sessione scaduta: URL non riconosciuto e nessun elemento WebApp")
    return True


def ensure_session(
    page: "Page",
    auth: "AuthManager",
    controller,
    get_credentials_fn: Callable[[], tuple[str, str]] | None = None,
    timeout_ms: int = 5000,
) -> None:
    """Verifica la sessione e tenta il recupero se scaduta.

    Flusso:
      1. Se non è scaduta (siamo sulla webapp) e is_logged_in → return
      2. Se non è scaduta ma is_logged_in fallisce → reload e riprova
      3. Se dopo il reload ancora non loggato, o URL è login → re-authenticate
    """
    from browser.auth import AuthError

    # 0. Check per modali critici EA (es. Cannot Authenticate). 
    # Se presente, lo accetta (clicca Ok) e forza il logout immediato.
    modal_handled = auth.check_and_handle_disconnect_modal(page)
    
    if modal_handled:
        logger.warning("Sessione invalidata dal server (Cannot Authenticate). Avvio re-login immediato.")
        # Il modale è stato gestito, attendi che la pagina di login sia pronta
        # e forza un re-autenticazione completa
        try:
            current_url = page.url
            logger.info(f"Dopo modale, URL attuale: {current_url}")
            
            # Se siamo su signin.ea.com, siamo pronti per il login
            # Altrimenti, naviga esplicitamente alla WebApp per far comparire il bottone Login
            if "signin.ea.com" not in current_url.lower():
                logger.info("Redirect al login page non completato, navigazione forzata...")
                controller.navigate_to_webapp()
                page.wait_for_timeout(3000)
        except Exception as e:
            logger.debug(f"Errore durante attesa post-modale: {e}")
        
        # Forza re-autenticazione
        logger.warning("Avvio procedura di re-login dopo modale...")
        try:
            from main import authenticate
            authenticate(controller, auth, page)
            logger.info("Sessione ripristinata con successo")
        except AuthError:
            raise
        except Exception as e:
            raise AuthError(f"Recupero sessione fallito in modo inatteso: {e}") from e
        return
    
    # 1. Se non c'è modale, controlla se la sessione è scaduta
    if not is_session_expired(page):
        if auth.is_logged_in(page, timeout_ms=timeout_ms):
            return
        # Sessione incerta: potrebbe essere solo caricamento lento o modale non intercettato
        logger.warning("Sessione incerta, tentativo di ricaricamento...")
        page.reload()
        page.wait_for_timeout(3000)
        # Riprova il check del modale dopo il reload
        if auth.check_and_handle_disconnect_modal(page):
            logger.warning("Modale rilevato dopo reload. Avvio re-login...")
            try:
                from main import authenticate
                authenticate(controller, auth, page)
                logger.info("Sessione ripristinata con successo")
            except AuthError:
                raise
            except Exception as e:
                raise AuthError(f"Recupero sessione fallito in modo inatteso: {e}") from e
            return
        
        if not is_session_expired(page) and auth.is_logged_in(page, timeout_ms=timeout_ms):
            return
        # Dopo reload ancora non loggato: cade nel blocco di re-auth sotto
    
    logger.warning("Sessione non valida, tento il ripristino (incluso eventuale controllo console)...")
    try:
        from main import authenticate
        authenticate(controller, auth, page)
        logger.info("Sessione ripristinata con successo")
    except AuthError:
        raise
    except Exception as e:
        raise AuthError(f"Recupero sessione fallito in modo inatteso: {e}") from e

"""Error handler with retry logic and session recovery.

Wraps Playwright actions with tenacity-based exponential backoff.
Provides session expiry detection and element-not-found fallbacks.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_on_timeout(func: Callable[..., T]) -> Callable[..., T]:
    """Decora una funzione con retry esponenziale per errori Playwright.

    Riprova fino a 3 volte con backoff esponenziale (2-30s).
    Logga warning in italiano prima di ogni retry.
    """
    def _before_sleep(retry_state):
        attempt = retry_state.attempt_number
        next_sleep = retry_state.next_action.sleep if retry_state.next_action else "?"
        logger.warning(
            f"Tentativo {attempt} fallito, riprovo tra {next_sleep:.1f}s..."
        )

    @retry(
        retry=retry_if_exception_type((PlaywrightError, PlaywrightTimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
        before_sleep=_before_sleep,
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def is_session_expired(page: "Page") -> bool:
    """Verifica se la sessione è scaduta controllando lo stato della pagina.

    Ritorna True se:
    - L'URL contiene "login"
    - L'elemento .ut-app non è presente
    - L'elemento .ea-app non è presente
    """
    url = page.url.lower()
    if "login" in url:
        logger.info("Sessione scaduta: URL contiene 'login'")
        return True

    ut_app = page.query_selector(".ut-app")
    if ut_app is None:
        logger.info("Sessione scaduta: elemento .ut-app non trovato")
        return True

    ea_app = page.query_selector(".ea-app")
    if ea_app is None:
        logger.info("Sessione scaduta: elemento .ea-app non trovato")
        return True

    return False


def handle_element_not_found(
    page: "Page",
    selector: str,
    timeout: int = 5000,
    fallback_reload: bool = True,
) -> bool:
    """Tenta di trovare un elemento, ricaricando la pagina se necessario.

    Ritorna True se l'elemento viene trovato, False altrimenti.
    """
    element = page.query_selector(selector)
    if element is not None:
        return True

    if fallback_reload:
        logger.warning(f"Elemento '{selector}' non trovato, ricarico la pagina...")
        page.reload()
        page.wait_for_timeout(3000)

        element = page.query_selector(selector)
        if element is not None:
            logger.info(f"Elemento '{selector}' trovato dopo ricaricamento")
            return True

    logger.error(f"Elemento '{selector}' non trovato nemmeno dopo ricaricamento")
    return False


def ensure_session(
    page: "Page",
    auth,
    controller,
    get_credentials_fn: Callable[[], tuple[str, str]] | None = None,
) -> bool:
    """Verifica la sessione e tenta il recupero se scaduta.

    Ritorna True se la sessione è valida o recuperata, False altrimenti.
    get_credentials_fn: callable che ritorna (email, password).
    """
    if not is_session_expired(page):
        return True

    logger.warning("Sessione non valida, tentativo di recupero...")
    try:
        auth.delete_saved_session()
        page.reload()
        page.wait_for_timeout(3000)

        if not auth.wait_for_login_page(page):
            logger.error("Pagina di login non trovata durante recupero")
            return False

        if get_credentials_fn is None:
            logger.error("Nessuna funzione credenziali fornita per il recupero")
            return False

        email, password = get_credentials_fn()
        if auth.perform_login(page, email, password):
            auth.save_session(controller.context)
            logger.info("Sessione recuperata con successo")
            return True
    except Exception as e:
        logger.error(f"Recupero sessione fallito: {e}")

    return False

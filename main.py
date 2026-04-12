"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import random
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from browser.controller import BrowserController
from browser.auth import AuthManager, AuthError
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
from browser.relist import RelistExecutor
from browser.rate_limiter import RateLimiter
from browser.error_handler import ensure_session
from bot_state import BotState
from telegram_handler import TelegramHandler
from browser.sold_handler import SoldHandler
from config.config import ConfigManager
from models.listing import ListingState, ListingScanResult
from models.action_log import JsonFormatter
from notifier import send_telegram_alert, send_telegram_photo

# ---------------------------------------------------------------------------
# Costanti Golden Hour — unica fonte di verità
# ---------------------------------------------------------------------------
GOLDEN_HOURS: tuple[int, ...] = (16, 17, 18)
GOLDEN_MINUTE: int = 10          # :10 di ogni golden hour
GOLDEN_PRE_NAV_MINUTE: int = 9   # navigazione pre-golden a :09:30
GOLDEN_RELIST_WINDOW: range = range(9, 12)   # :09 → :11 inclusi
GOLDEN_CLOSE_WINDOW: range = range(8, 13)    # :08 → :12 "vicino alla golden"
GOLDEN_PERIOD_START: tuple[int, int] = (15, 10)  # 15:10
GOLDEN_PERIOD_END: tuple[int, int] = (18, 15)    # 18:15

EA_WEBAPP_URL = "https://www.ea.com/fifa/ultimate-team/web-app/"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
action_logger = logging.getLogger("actions")


def setup_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

    # Logger azioni strutturato (JSON) → logs/actions.jsonl
    actions_file_handler = logging.FileHandler(
        log_dir / "actions.jsonl", mode="a", encoding="utf-8"
    )
    actions_file_handler.setLevel(logging.INFO)
    actions_file_handler.setFormatter(JsonFormatter())
    action_logger.setLevel(logging.INFO)
    action_logger.addHandler(actions_file_handler)
    action_logger.propagate = False


# ---------------------------------------------------------------------------
# Utilità UI
# ---------------------------------------------------------------------------
def format_duration(seconds: int) -> str:
    """Formatta i secondi in stringa leggibile (es. '18 min', '1 min 30 s')."""
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} min {s} s" if s > 0 else f"{m} min"
    h, m = divmod(m, 60)
    return f"{h}h {m} min"


def make_status_table(phase: str, scanned: int, relisted: int, errors: int, cycle: int = 0) -> Table:
    current_time = datetime.now().strftime("%H:%M:%S")
    cycle_label = f" | Ciclo {cycle}" if cycle else ""
    table = Table(title=f"FIFA Auto-Relist [🕒 {current_time}{cycle_label}]")
    table.add_column("Fase", style="cyan")
    table.add_column("Scansionati", justify="right")
    table.add_column("Rilistati", justify="right", style="green")
    table.add_column("Errori", justify="right", style="red")
    table.add_row(phase, str(scanned), str(relisted), str(errors))
    return table


# ---------------------------------------------------------------------------
# Credenziali
# ---------------------------------------------------------------------------
def get_credentials() -> tuple[str, str]:
    email = os.environ.get("FIFA_EMAIL")
    password = os.environ.get("FIFA_PASSWORD")

    if email and password:
        return email, password

    raise RuntimeError("Credenziali FIFA_EMAIL o FIFA_PASSWORD non trovate nel file .env")


# ---------------------------------------------------------------------------
# Autenticazione
# ---------------------------------------------------------------------------
def authenticate(controller, auth, page) -> None:
    """Gestisce il flusso di login o ripristino sessione. Solleva AuthError su fallimento.

    Se la WebApp mostra 'Signed Into Another Device' (sessione PS5/console attiva),
    aspetta pazientemente in loop invece di andare in crash.
    """
    logger = logging.getLogger(__name__)

    if auth.has_saved_session():
        logger.info("Sessione salvata trovata, verifica in corso...")
        page.wait_for_timeout(2000)

    # --- Gestione sessione console e Login ---
    # EA a volte droppa la sessione dopo ore di inattività mostrandoci solo la landing page
    # (senza l'errore palese "Signed into another device"). Cliccando Login, se l'utente
    # sta ancora giocando, l'errore ricompare istantaneamente. Serviva un loop generale protettivo.
    CONSOLE_WAIT_SECONDS = 1800   # controlla ogni 30 minuti
    MAX_CONSOLE_WAIT_HOURS = 4    # aspetta al massimo 4 ore
    max_console_checks = (MAX_CONSOLE_WAIT_HOURS * 3600) // CONSOLE_WAIT_SECONDS
    console_checks = 0

    while True:
        # FASE 1: Pura attesa console attiva
        while auth.is_console_session_active(page):
            console_checks += 1
            waited_min = (console_checks * CONSOLE_WAIT_SECONDS) // 60
            logger.warning(
                f"[Console attiva] Sessione PS5/Console in uso. "
                f"Riprovo tra {CONSOLE_WAIT_SECONDS}s... "
                f"(attesa totale: ~{waited_min} min)"
            )
            if console_checks >= max_console_checks:
                raise AuthError(
                    f"Sessione console ancora attiva dopo {MAX_CONSOLE_WAIT_HOURS}h. "
                    "Esci da Ultimate Team sulla console e riavvia il bot."
                )
            time.sleep(CONSOLE_WAIT_SECONDS)

            logger.info("Ricarico la WebApp per ricontrollare lo stato della console...")
            controller.navigate_to_webapp()
            page.wait_for_timeout(5000)

            # Contromisura al session drop: EA ci farà scendere sulla Landing page generica.
            # Se ricaricando troviamo il tasto Login (invece dell'errore), lo premiamo per
            # generare l'esito reale: "Siamo loggati" o "La console è ancora occupata".
            login_btn = page.get_by_role("button", name="Login")
            if login_btn.count():
                logger.info("Pulsante Login trovato (Landing Page). Click per verificare stato console...")
                try:
                    login_btn.first.click(timeout=5000)
                except Exception as e:
                    logger.warning(f"Impossibile cliccare 'Login' (timeout o elemento instabile): {e}")
                # Aspettiamo 5 secondi invece di 8, se è console occupata il pop-up appare subito
                page.wait_for_timeout(5000)

        # FASE 2: La console non mostra allarmi attivi. Vediamo se siamo già attivamente loggati
        if auth.is_logged_in(page, timeout_ms=5000):
            logger.info("Già loggato con sessione salvata (o ripristino automatico riuscito).")
            auth.save_session(controller.context)
            return

        # FASE 3: Procedi con il login manuale formale
        url = page.url.lower()
        if "signin.ea.com" in url:
            logger.info("Reindirizzamento automatico alla pagina di login EA rilevato")
        else:
            logger.info("Login richiesto dalla landing page...")
            if not auth.wait_for_login_page(page, timeout=10000):
                logger.warning("Pulsante Login non rilevato, provo comunque ad andare avanti...")

        email, password = get_credentials()

        success = auth.perform_login(page, email, password)

        if success:
            auth.save_session(controller.context)
            logger.info("Login completato e sessione salvata")
            return
        else:
            # Se ha fallito potremmo aver appena riscoperto la sessione console annidata post-login
            if auth.is_console_session_active(page):
                logger.warning("Rilevata sessione console attiva ORA, in fase di login formale. Riprendo ad attendere...")
                continue  # Torna al "while True" e rientra nel "while auth.is_console_session_active"

            # Se ha fallito e non è colpa della console... è un errore puro (credenziali o caricamento)
            raise AuthError("Login fallito (non a causa della console)")


# ---------------------------------------------------------------------------
# Navigazione
# ---------------------------------------------------------------------------
def navigate_with_retry(navigator, page) -> bool:
    """Naviga al Transfer List con un retry su timeout."""
    logger = logging.getLogger(__name__)

    try:
        return navigator.go_to_transfer_list()
    except Exception as e:
        logger.warning(f"Timeout navigazione, riprovo: {e}")
        page.reload()
        page.wait_for_timeout(3000)
        try:
            return navigator.go_to_transfer_list()
        except Exception as e2:
            logger.error(f"Secondo tentativo fallito: {e2}")
            return False


# ---------------------------------------------------------------------------
# Relist
# ---------------------------------------------------------------------------
def relist_expired_listings(executor, expired_listings) -> tuple[int, int]:
    """Esegue il rilist dei listing scaduti e logga ogni azione. Ritorna (succeeded, failed)."""
    logger = logging.getLogger(__name__)
    succeeded = 0
    failed = 0
    total = len(expired_listings)

    for listing in expired_listings:
        result = executor.relist_single(listing)
        if result.success:
            succeeded += 1
            action_logger.info(
                "Rilist completato",
                extra={"action": "relist", "player_name": result.player_name, "success": True},
            )
        else:
            failed += 1
            action_logger.warning(
                "Rilist fallito",
                extra={"action": "relist", "player_name": result.player_name, "success": False, "error": result.error},
            )
        logger.info(f"Progresso Rilist: {succeeded + failed}/{total}")

    return succeeded, failed


# ---------------------------------------------------------------------------
# Logica Golden Hour
# ---------------------------------------------------------------------------
def get_min_active_seconds(scan: ListingScanResult) -> int | None:
    """Restituisce il tempo minimo rimanente tra i listing attivi."""
    active_times = [
        l.time_remaining_seconds
        for l in scan.listings
        if l.state == ListingState.ACTIVE
        and l.time_remaining_seconds is not None
        and l.time_remaining not in ("---", "Expired", "Scaduto")
    ]
    return min(active_times) if active_times else None


def get_active_with_timer_count(scan: ListingScanResult) -> int:
    """Conta gli attivi che hanno un timer reale (esclusi quelli con '--')."""
    return sum(
        1 for l in scan.listings
        if l.state == ListingState.ACTIVE
        and l.time_remaining_seconds is not None
        and l.time_remaining not in ("---", "Expired", "Scaduto")
    )


def get_next_golden_hour(now: datetime) -> datetime | None:
    """Restituisce il prossimo target :10 (16:10, 17:10, 18:10) come datetime.

    Se siamo dopo le 18:10, restituisce None (nessuna golden oggi).
    Se siamo prima delle 16:10, restituisce 16:10.
    Se siamo tra 16:10-17:10, restituisce 17:10.
    Se siamo tra 17:10-18:10, restituisce 18:10.
    """
    golden_targets = [
        now.replace(hour=h, minute=GOLDEN_MINUTE, second=0, microsecond=0)
        for h in GOLDEN_HOURS
    ]
    for target in golden_targets:
        if now < target:
            return target
    return None


def is_in_golden_period(now: datetime) -> bool:
    """True se siamo nella fascia 15:10 → 18:15.

    In questa fascia il golden sync è attivo: il bot aspetta SEMPRE
    la prossima golden hour (16:10, 17:10, 18:10) prima di navigare.
    """
    start_h, start_m = GOLDEN_PERIOD_START
    end_h, end_m = GOLDEN_PERIOD_END
    hour, minute = now.hour, now.minute

    if hour < start_h or (hour == start_h and minute < start_m):
        return False
    if hour > end_h or (hour == end_h and minute > end_m):
        return False
    return True


def is_in_hold_window(now: datetime) -> bool:
    """True se siamo nella fascia golden ma NON nel momento del relist (:09-:11).

    Durante la fascia 15:10→18:15, il relist è consentito SOLO nella finestra:
    - :09 → :11 delle ore 16, 17, 18 (pre-nav + relist :10 + ritardatari :11)
    Tutto il resto è HOLD: gli scaduti aspettano la prossima golden.

    Fuori dalla fascia 15:10-18:15: relist normale (sempre False).
    """
    if not is_in_golden_period(now):
        return False

    # Finestra relist: :09-:11 delle GOLDEN_HOURS
    if now.hour in GOLDEN_HOURS and now.minute in GOLDEN_RELIST_WINDOW:
        return False  # Momento del relist golden

    return True


def is_close_to_golden(now: datetime) -> bool:
    """True se siamo a ridosso della golden hour (:08-:12 delle GOLDEN_HOURS)."""
    return now.hour in GOLDEN_HOURS and now.minute in GOLDEN_CLOSE_WINDOW


def is_in_golden_window(now: datetime) -> bool:
    """True se siamo nella finestra di relist golden (:09-:11 delle GOLDEN_HOURS)."""
    return now.hour in GOLDEN_HOURS and now.minute in GOLDEN_RELIST_WINDOW


# ---------------------------------------------------------------------------
# Notifiche
# ---------------------------------------------------------------------------
def _send_batch_notification(
    app_config,
    page,
    accumulator: dict,
    last_relist_error: str | None,
    logger: logging.Logger,
) -> None:
    """Invia il report Telegram aggregato e pulisce lo screenshot."""
    if not app_config.notifications.telegram_token:
        return

    screenshot_path = "relist_report.png"
    try:
        page.screenshot(path=screenshot_path)
        error_msg = f" ⚠️ Error: {last_relist_error}" if last_relist_error else ""
        msg = (
            f"🔔 Report Aggregato\n"
            f"-------------------\n"
            f"📦 Cicli: {accumulator['cycles']}\n"
            f"🚀 Totale Rilistati: {accumulator['relisted']}\n"
            f"❌ Falliti: {accumulator['failed']}{error_msg}\n"
            f"🕒 Modalità: ⚽ Drift Ibrido"
        )
        send_telegram_photo(app_config.notifications, screenshot_path, msg)
    except Exception as e:
        logger.error(f"Errore invio notifica: {e}")
    finally:
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)


# ---------------------------------------------------------------------------
# Loop principale
# ---------------------------------------------------------------------------
def _handle_session_recovery(executor, auth, config, page, fifa_logger: logging.Logger) -> bool:
    """Tenta di recuperare la sessione dopo un errore di relist. Ritorna True se serve `continue`."""
    if executor.check_session_valid():
        return False

    fifa_logger.warning("Sessione non valida - tentativo refresh...")
    page.reload()
    page.wait_for_timeout(3000)

    if executor.check_session_valid():
        return False

    fifa_logger.warning("Refresh fallito - logout e riavvio")
    auth_mgr = AuthManager(config)
    auth_mgr.delete_saved_session()
    page.goto(EA_WEBAPP_URL)
    page.wait_for_timeout(3000)
    return True  # caller deve fare `continue`


def _save_error_screenshot(page, logger: logging.Logger) -> None:
    """Salva uno screenshot di errore con timestamp e lo rimuove dopo averlo loggato."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"relist_error_{ts}.png"
    try:
        page.screenshot(path=screenshot_path)
        logger.info(f"Screenshot errore salvato: {screenshot_path}")
    except Exception as e:
        logger.warning(f"Impossibile salvare screenshot: {e}")


def _compute_next_wait(
    scan: ListingScanResult,
    now: datetime,
    fifa_logger: logging.Logger,
) -> int:
    """Calcola il wait ottimale dopo un relist riuscito."""
    if is_in_golden_window(now):
        wait = 10
        fifa_logger.info(f"Golden Hour: polling rapido per ritardatari in {format_duration(wait)}.")
        return wait

    min_active = get_min_active_seconds(scan)
    if min_active is not None:
        wait = max(min_active - 20, 10)
        fifa_logger.info(f"Prossimo expiry tra {format_duration(min_active)}. Wait: {format_duration(wait)}")
        return wait

    # Nessun timer visibile: potrebbero esserci item in "Processing..."
    processing_count = sum(
        1 for l in scan.listings
        if l.state == ListingState.ACTIVE
        and l.time_remaining in ("Processing...", "Elaborazione...")
    )

    if is_in_hold_window(now):
        ng = get_next_golden_hour(now)
        if ng:
            wait = min(60, int((ng.replace(minute=GOLDEN_PRE_NAV_MINUTE, second=30) - now).total_seconds()))
            fifa_logger.info(f"[HOLD] In hold, check tra {format_duration(wait)} per golden delle {ng.strftime('%H:%M')}.")
        else:
            wait = 3600 - 20
            fifa_logger.info(f"Tutti relistati. Wait: {format_duration(wait)}")
        return wait

    if processing_count > 0:
        wait = 30
        fifa_logger.info(f"{processing_count} oggetti in Processing... Polling ogni {format_duration(wait)}.")
        return wait

    wait = 3600 - 20
    fifa_logger.info(f"Tutti relistati. Wait: {format_duration(wait)}")
    return wait


def _active_wait_with_heartbeat(
    wait_seconds: int,
    page,
    auth,
    bot_state: BotState,
    logger: logging.Logger
) -> bool:
    """Attesa in chunk: ogni ~3 minuti esegue un refresh della pagina (Heartbeat).
    Usa il pulsante 'Clear Sold' invece di ricaricare la pagina per non perdere
    lo stato di navigazione, forzando comunque EA a validare la sessione.
    
    Interrompe l'attesa in anticipo se la sessione cade.
    Ritorna True se un reboot è stato richiesto.
    """
    waited = 0
    
    while waited < wait_seconds:
        remaining = wait_seconds - waited
        # Intervallo casuale tra 2.5 e 5 minuti per non essere prevedibili
        current_heartbeat_interval = random.randint(150, 300)
        current_wait = min(current_heartbeat_interval, remaining)
        
        # Attesa passiva per questo chunk
        if bot_state.wait_interruptible(current_wait):
            return True  # Reboot richiesto
            
        waited += current_wait
        
        # Esegui l'heartbeat solo se non abbiamo finito l'attesa e non siamo in pausa/console mode
        if waited < wait_seconds and not bot_state.is_paused() and not bot_state.is_console_mode():
            logger.info("💓 Heartbeat: clicco 'Clear Sold' per verificare la tenuta della sessione...")
            try:
                # Clicca "Clear Sold" (versione EN e IT) che invia una call al backend
                clear_btn = page.get_by_role("button", name="Clear Sold Items")
                if not clear_btn.count():
                    clear_btn = page.get_by_role("button", name="Cancella oggetti venduti")
                if not clear_btn.count():
                    clear_btn = page.locator('button:has-text("Clear Sold"), button:has-text("Cancella")')

                if clear_btn.count() and clear_btn.first.is_visible(timeout=3000):
                    clear_btn.first.click(timeout=3000)
                    page.wait_for_timeout(2000)
                    
                    # Nel caso la sessione sia attiva ma esca un popup di conferma, lo annulliamo
                    # per non consumare i sold item fuori dal SoldHandler
                    cancel_btn = page.get_by_role("button", name="Cancel")
                    if not cancel_btn.count():
                        cancel_btn = page.get_by_role("button", name="Annulla")
                    if cancel_btn.count() and cancel_btn.first.is_visible(timeout=1000):
                        cancel_btn.first.click(timeout=2000)
                        logger.debug("Heartbeat: dialog Clear Sold annullato correttamente")
                else:
                    logger.debug("Pulsante Clear Sold non trovato (forse non siamo in Transfer List?), skiplo.")
                    
                page.wait_for_timeout(2000)
                
                # EA ha kickato la webapp mostrando l'errore console
                if auth.is_console_session_active(page):
                    logger.warning("Heartbeat ha rilevato la console in uso! Interrompo attesa per gestire il blocco.")
                    break
                    
                # L'errore console non c'è, ma siamo fuori dalla WebApp (es. landing page di login)
                if not auth.is_logged_in(page, timeout_ms=3000):
                    logger.warning("Heartbeat ha rilevato che la sessione è scaduta o richiede autenticazione. Interrompo attesa.")
                    break
                    
            except Exception as e:
                logger.debug(f"Errore durante l'heartbeat (ignorato): {e}")

    return False


def _golden_hold_loop(
    now: datetime,
    next_golden: datetime,
    page,
    auth,
    controller,
    status_console: Console,
    logger: logging.Logger,
    cycle: int,
    bot_state,
) -> datetime | None:
    """Aspetta in loop fino al pre-nav della golden hour, verificando la sessione ogni chunk.

    Ritorna il next_golden aggiornato, o None se siamo usciti dalla fascia.
    """
    pre_nav_time = next_golden.replace(minute=GOLDEN_PRE_NAV_MINUTE, second=30, microsecond=0)
    seconds_until_golden = (next_golden - now).total_seconds()
    seconds_until_pre_nav = (pre_nav_time - now).total_seconds()

    while seconds_until_pre_nav > 0:
        wait_chunk = max(1, min(3600, int(seconds_until_pre_nav)))
        status_console.print(make_status_table("Pausa Sincro Golden", 0, 0, 0, cycle))
        logger.info(
            f"[Golden] HOLD: mancano {format_duration(int(seconds_until_golden))} "
            f"alle {next_golden.strftime('%H:%M')}. Mantengo sessione attiva..."
        )
        
        # Usa l'heartbeat invece dello sleep passivo per reagire subito a logout/console
        if _active_wait_with_heartbeat(wait_chunk, page, auth, bot_state, logger):
            logger.info("[Reboot] HOLD interrotto per reboot richiesto.")
            return next_golden # Ritorna per permettere il reboot nel main loop

        now = datetime.now()
        next_golden = get_next_golden_hour(now)
        if next_golden is None:
            return None  # Usciti dalla fascia golden

        pre_nav_time = next_golden.replace(minute=GOLDEN_PRE_NAV_MINUTE, second=30, microsecond=0)
        seconds_until_golden = (next_golden - now).total_seconds()
        seconds_until_pre_nav = (pre_nav_time - now).total_seconds()

        # Verifica finale della sessione (veloce se già loggato)
        ensure_session(page, auth, controller, get_credentials)

    return next_golden


def main() -> None:
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    fifa_logger = logging.getLogger("fifa")
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")

    controller = None
    app_config = None
    telegram = None

    # status_console disponibile prima del loop (usata anche nel blocco console-check)
    status_console = Console()

    try:
        cm = ConfigManager()
        app_config = cm.load()
        config = app_config.to_dict()
        logger.info(
            f"Config caricata (intervallo: {app_config.scan_interval_seconds}s, "
            f"modalità: {app_config.listing_defaults.relist_mode})"
        )

        send_telegram_alert(
            app_config.notifications,
            "✅ FIFA 26 Auto-Relist Tool avviato con successo! Notifiche Telegram attivate."
        )

        controller = BrowserController(config)
        auth = AuthManager(config)

        # Prova a ripristinare il profilo browser esistente
        profile_dir = auth.load_session()
        page = controller.start(user_data_dir=profile_dir)

        controller.navigate_to_webapp()
        logger.info(f"WebApp caricata: {page.title()}")

        authenticate(controller, auth, page)
        logger.info("=== Autenticazione completata ===")
        
        # Notifica Telegram di login riuscito
        login_time = datetime.now().strftime("%H:%M:%S")
        send_telegram_alert(
            app_config.notifications,
            f"✅ Login FIFA riuscito!\n🕒 Orario: {login_time}\n🚀 Bot pronto per il rilist"
        )

        navigator = TransferMarketNavigator(page, config)
        detector = ListingDetector(page)
        executor = RelistExecutor(page, config)
        rate_limiter = RateLimiter(
            min_delay_ms=app_config.rate_limiting.min_delay_ms,
            max_delay_ms=app_config.rate_limiting.max_delay_ms,
        )
        cycle = 0

        # --- BotState & Telegram integration ---
        bot_state = BotState()

        if app_config.notifications.telegram_token and app_config.notifications.telegram_chat_id:
            telegram = TelegramHandler(
                token=app_config.notifications.telegram_token,
                chat_id=app_config.notifications.telegram_chat_id,
                bot_state=bot_state,
                page=page,
                log_dir=Path(__file__).parent / "logs",
            )
            # Wire SoldHandler per il comando /del_sold
            sold_handler = SoldHandler(page, config)
            telegram.set_sold_handler(sold_handler)
            telegram.start()
            logger.info("Telegram handler avviato")

        # Notification batching — dichiarati FUORI dal loop (persistono tra i cicli)
        last_notification_time: datetime | None = None
        last_relist_error: str | None = None
        notification_accumulator = {"relisted": 0, "failed": 0, "cycles": 0}
        NOTIFICATION_INTERVAL = 300   # invia ogni 5 minuti max
        NOTIFICATION_THRESHOLD = 5    # oppure quando >= 5 item accumulati

        logger.info(
            f"Avvio loop continuo (intervallo: {app_config.scan_interval_seconds}s). "
            "Premi Ctrl+C per fermare."
        )

        while True:
            cycle += 1
            logger.info(f"=== Ciclo {cycle} ===")

            # Check if bot is in console mode (deep sleep)
            if bot_state.is_console_mode():
                until = bot_state.get_console_mode_until()
                until_str = f" (auto-resume alle {until.strftime('%H:%M')})" if until else ""
                logger.info(f"[Console Mode] 🎮 Deep sleep{until_str} — zero interazione WebApp")
                status_console.print(make_status_table("🎮 Console Mode", 0, 0, 0, cycle))
                time.sleep(30)
                continue

            # Check if bot is paused via Telegram
            if bot_state.is_paused():
                logger.info("[Telegram] Bot in pausa — skip scanning")
                status_console.print(make_status_table("⏸️ In Pausa (Telegram)", 0, 0, 0, cycle))
                time.sleep(10)
                continue

            # Check if reboot was requested via Telegram
            if bot_state.is_reboot_requested():
                logger.info("[Telegram] Reboot richiesto — uscita dal loop principale...")
                break

            # Process queued Telegram commands (e.g., /del_sold)
            while bot_state.has_commands():
                cmd = bot_state.get_next_command()
                if cmd:
                    cmd_type = cmd.get("type")
                    callback = cmd.get("callback")
                    if cmd_type == "del_sold" and callback:
                        logger.info("[Telegram] Eseguo comando /del_sold in coda...")
                        result = callback()
                        if result.success:
                            send_telegram_alert(
                                app_config.notifications,
                                f"🧹 Pulizia completata: {result.items_cleared} oggetti, {result.total_credits:,} crediti raccolti"
                            )
                        else:
                            send_telegram_alert(
                                app_config.notifications,
                                f"❌ Pulizia fallita: {result.error}"
                            )

            ensure_session(page, auth, controller, get_credentials)

            # Gestione sessione PS5/Console attiva nel loop
            if auth.is_console_session_active(page):
                wait_console = 1800  # 30 minuti
                logger.info(f"Sessione console rilevata. Sospendo per {wait_console}s...")
                status_console.print(make_status_table("Console Attiva", 0, 0, 0, cycle))
                time.sleep(wait_console)
                page.reload()  # Ricarica per vedere se la sessione è libera
                continue

            # --- HYBRID GOLDEN SYNC LOGIC ---
            now = datetime.now()
            next_golden = get_next_golden_hour(now)

            if next_golden and is_in_golden_period(now) and not is_in_golden_window(now):
                pre_nav_time = next_golden.replace(minute=GOLDEN_PRE_NAV_MINUTE, second=30, microsecond=0)
                seconds_until_pre_nav = (pre_nav_time - now).total_seconds()
                seconds_until_golden = (next_golden - now).total_seconds()

                if seconds_until_pre_nav > 0:
                    # HOLD: aspetta fino al pre-nav (con session-check ogni 5 minuti)
                    next_golden = _golden_hold_loop(
                        now, next_golden, page, auth, controller, status_console, logger, cycle, bot_state
                    )
                    if next_golden is None:
                        pass  # Fuori fascia golden, procedi con navigazione normale
                    else:
                        logger.info("[Golden] PRE-NAV AVVIATA! Navigo ora per arrivare al :10 preciso.")
                elif 0 < seconds_until_golden <= 30:
                    logger.info(f"[Golden] Timing perfetto! Mancano {int(seconds_until_golden)}s al :10, procedo.")
                # else: siamo dopo il :10, naviga normalmente

            if not navigate_with_retry(navigator, page):
                status_console.print(make_status_table("Errore Navigazione", 0, 0, 0, cycle))
                rate_limiter.wait()
                continue

            # --- WAIT FOR EXACT GOLDEN TIME ---
            now = datetime.now()
            next_golden = get_next_golden_hour(now)
            if next_golden and is_in_golden_period(now) and now < next_golden:
                # Only wait if we're NOT already in a golden relist window (:09-:11)
                if not is_in_golden_window(now):
                    wait_secs = (next_golden - now).total_seconds()
                    logger.info(f"[Golden] Attesa precisa: {format_duration(int(wait_secs))} per le {next_golden.strftime('%H:%M:%S')}.")
                    time.sleep(wait_secs)
                else:
                    logger.info(f"[Golden] Già nella finestra golden ({now.strftime('%H:%M:%S')}), procedo con scansione immediata.")

            fifa_logger.info(f"--- [SCANSIONE IBRIDA] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")
            scan = detector.scan_listings()

            succeeded = 0
            failed = 0
            next_wait = 600  # default fallback

            # --- RILEVAMENTO RELIST MANUALE ---
            # Se alla golden hour tutti gli item hanno timer simile (~17-21 min),
            # qualcuno ha già relistato manualmente → il bot si ritira.
            now_scan = datetime.now()
            if (
                scan.active_count > 0
                and scan.expired_count == 0
                and is_in_golden_window(now_scan)
            ):
                active_times = [
                    l.time_remaining_seconds
                    for l in scan.listings
                    if l.state == ListingState.ACTIVE
                    and l.time_remaining_seconds is not None
                ]
                if active_times:
                    min_t = min(active_times)
                    max_t = max(active_times)
                    # Se i timer sono tutti tra 15-22 minuti e la differenza tra max e min
                    # è piccola (≤90s), significa che sono stati relistati tutti insieme.
                    if 900 <= min_t <= 1320 and (max_t - min_t) <= 90:
                        fifa_logger.info(
                            f"[⚠️ RELIST MANUALE RILEVATO] Tutti gli item hanno timer simile "
                            f"({min_t//60}-{max_t//60} min). Qualcuno ha già relistato."
                        )
                        fifa_logger.info(
                            f"Bot si ritira. Prossimo check tra {format_duration(min_t - 20)}."
                        )
                        next_wait = max(min_t - 20, 60)
                        logger.info(f"Fine ciclo {cycle}. In attesa per {format_duration(next_wait)}...")
                        rate_limiter.wait()
                        if _active_wait_with_heartbeat(int(next_wait), page, auth, bot_state, logger):
                            logger.info("[Reboot] Sleep interrotto — reboot immediato!")
                            break
                        continue

            if scan.expired_count > 0:
                in_hold = is_in_hold_window(datetime.now())
                force_relist = bot_state.consume_force_relist()

                if in_hold and not force_relist:
                    next_g = get_next_golden_hour(datetime.now())
                    if next_g is not None:
                        # Genuine hold: there's a future golden coming
                        fifa_logger.info(f"[HOLD] {scan.expired_count} scaduti rilevati ma in HOLD WINDOW.")
                        fifa_logger.info(f"[HOLD] Prossima golden: {next_g.strftime('%H:%M')}. Relist rimandato.")
                        next_wait = 60
                    else:
                        # No more goldens today — override hold, relist immediately
                        logger.info("[Golden] Fascia golden terminata, nessuna golden futura. Relist immediato.")
                        fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti (post-golden). Rilisto...")
                        # Proceed to relist (fall through to else block)
                        in_hold = False

                else:
                    # Relist SEMPRE — sia in free drift che in golden window
                    if force_relist:
                        logger.info("[Telegram] Force relist — bypass hold window")
                    fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti. Rilisto...")

                    if executor.relist_mode == "all":
                        batch = executor.relist_all(count=scan.expired_count)
                        succeeded = batch.succeeded
                        failed = batch.total - batch.succeeded
                        if batch.relist_error:
                            last_relist_error = batch.relist_error
                            fifa_logger.error(f"ERRORE RELIST: {last_relist_error}")
                            _save_error_screenshot(page, fifa_logger)
                            if _handle_session_recovery(executor, auth, config, page, fifa_logger):
                                continue
                    else:
                        expired = [l for l in scan.listings if l.needs_relist]
                        succeeded, failed = relist_expired_listings(executor, expired)

                    fifa_logger.info(f"Relist completato: {succeeded} successi, {failed} falliti.")
                    bot_state.update_stats(cycle=cycle, relisted=succeeded, failed=failed)
                    next_wait = _compute_next_wait(scan, datetime.now(), fifa_logger)

            else:
                fifa_logger.info("Nessun oggetto scaduto trovato.")
                now_ne = datetime.now()
                min_active = get_min_active_seconds(scan)

                if is_close_to_golden(now_ne) and (min_active is not None and min_active < 120):
                    next_wait = 15
                    fifa_logger.info(f"Prossimità Golden: item scade tra {min_active}s, polling rapido.")
                elif is_in_hold_window(now_ne):
                    next_g = get_next_golden_hour(now_ne)
                    if next_g:
                        secs = (next_g.replace(minute=GOLDEN_PRE_NAV_MINUTE, second=30) - now_ne).total_seconds()
                        next_wait = min(max(int(secs), 30), 300)
                        fifa_logger.info(f"[HOLD] Nessuno scaduto. Prossima golden: {next_g.strftime('%H:%M')}. Check tra {format_duration(next_wait)}.")
                    else:
                        next_wait = 300
                elif min_active is not None:
                    next_wait = max(min_active - 20, 10)
                    fifa_logger.info(f"Prossimo expiry tra {format_duration(min_active)}. Wait: {format_duration(next_wait)}")
                else:
                    # Check for Processing items before defaulting to 600s
                    processing_count = sum(
                        1 for l in scan.listings
                        if l.state == ListingState.ACTIVE
                        and l.time_remaining in ("Processing...", "Elaborazione...")
                    )
                    if processing_count > 0:
                        next_wait = 30
                        fifa_logger.info(f"{processing_count} oggetti in Processing... Polling ogni {format_duration(next_wait)}.")
                    else:
                        next_wait = 600
                        fifa_logger.info(f"Nessun oggetto in lista. Prossimo check tra {format_duration(next_wait)}.")

            # --- NOTIFICA FINALE UNIFICATA (BATCHING) ---
            if succeeded > 0 or failed > 0:
                logger.info(f"Ciclo completato. Totale: {succeeded} successi, {failed} fallimenti.")

                notification_accumulator["relisted"] += succeeded
                notification_accumulator["failed"] += failed
                notification_accumulator["cycles"] += 1

                now_notify = datetime.now()
                time_since_last = (
                    (now_notify - last_notification_time).total_seconds()
                    if last_notification_time else float("inf")
                )

                # Se il prossimo wait è breve (< 120s) significa che ci sono altri
                # oggetti in scadenza imminente. Accumuliamo e aspettiamo di rilistare
                # anche quelli prima di inviare UNA SOLA notifica.
                # Safety net: dopo 5 cicli rapidi consecutivi, forziamo la notifica.
                more_items_coming = next_wait <= 120 and notification_accumulator["cycles"] < 5

                should_notify = (
                    not more_items_coming
                    and (
                        time_since_last >= NOTIFICATION_INTERVAL
                        or notification_accumulator["relisted"] >= NOTIFICATION_THRESHOLD
                    )
                )

                if more_items_coming:
                    logger.info(
                        f"[Notifica] Accumulo: {notification_accumulator['relisted']} rilistati "
                        f"in {notification_accumulator['cycles']} cicli. "
                        f"Attendo altri scaduti tra {format_duration(next_wait)}..."
                    )

                if should_notify:
                    _send_batch_notification(app_config, page, notification_accumulator, last_relist_error, logger)
                    last_relist_error = None
                    notification_accumulator = {"relisted": 0, "failed": 0, "cycles": 0}
                    last_notification_time = now_notify

            # --- ATTESA PROSSIMO CICLO (interrompibile da /reboot o heartbeat) ---
            logger.info(f"Fine ciclo {cycle}. In attesa per {format_duration(next_wait)}...")
            rate_limiter.wait()
            if _active_wait_with_heartbeat(int(next_wait), page, auth, bot_state, logger):
                logger.info("[Reboot] Sleep interrotto — reboot immediato!")
                break

        # --- REBOOT HANDLING ---
        # Se arriviamo qui, il while True è stato interrotto da `break` (reboot)
        if bot_state.is_reboot_requested():
            logger.info("[Reboot] Shutdown pulito in corso...")

            if telegram:
                telegram.stop()
                logger.info("[Reboot] Telegram handler fermato")

            if controller and controller.is_running():
                controller.stop()
                logger.info("[Reboot] Browser chiuso")

            # Piccola pausa per assicurarsi che le risorse siano rilasciate
            time.sleep(2)

            # Spawn nuovo processo
            import subprocess
            main_path = Path(__file__).resolve()
            logger.info(f"[Reboot] Lancio nuovo processo: {sys.executable} {main_path}")

            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, str(main_path)],
                    cwd=str(main_path.parent),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(main_path)],
                    cwd=str(main_path.parent),
                    start_new_session=True,
                )

            logger.info("[Reboot] Processo corrente in uscita...")
            sys.exit(0)

    except AuthError as e:
        logger.error(f"Errore autenticazione: {e}")
        if app_config:
            send_telegram_alert(app_config.notifications, f"🚨 ERRORE FIFA BOT:\n{e}")
        if controller and controller.is_running():
            controller.stop()
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interruzione utente")
        if telegram:
            logger.info("Arresto Telegram handler...")
            telegram.stop()
        if controller and controller.is_running():
            controller.stop()
    except Exception as e:
        logger.error(f"Errore: {e}", exc_info=True)
        if app_config:
            send_telegram_alert(app_config.notifications, f"❌ ERRORE CRITICO INATTESO:\n{e}")
        if controller and controller.is_running():
            controller.stop()
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser with run, config e history subcommands."""
    parser = argparse.ArgumentParser(
        prog="fifa-relist",
        description="FIFA 26 Auto-Relist Tool",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Avvia il tool (default se nessun comando specificato)")

    config_parser = sub.add_parser("config", help="Gestisci la configurazione")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_sub.add_parser("show", help="Mostra le impostazioni correnti")
    set_parser = config_sub.add_parser("set", help="Aggiorna un'impostazione")
    set_parser.add_argument("key", help="Chiave dotted (es. listing_defaults.duration)")
    set_parser.add_argument("value", help="Nuovo valore")
    config_sub.add_parser("reset", help="Ripristina i valori predefiniti")

    history_parser = sub.add_parser("history", help="Mostra cronologia azioni")
    history_parser.add_argument(
        "-n", "--lines", type=int, default=20, help="Numero di voci da mostrare"
    )

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "config":
        cm = ConfigManager()
        if args.config_action == "show":
            cfg = cm.load()
            print(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False))
        elif args.config_action == "set":
            cm.set_value(args.key, args.value)
            print(f"OK: {args.key} = {args.value}")
        elif args.config_action == "reset":
            cm.reset_defaults()
            print("OK: Config reset to defaults")
        else:
            parser.parse_args(["config", "--help"])

    elif args.command == "history":
        from models.action_log import parse_action_history

        log_path = Path(__file__).parent / "logs" / "actions.jsonl"
        entries = parse_action_history(log_path, args.lines)

        if not entries:
            print("Nessuna cronologia azioni trovata.")
        else:
            for entry in entries:
                ts = entry.get("timestamp", "?")
                indicator = "OK" if entry.get("success", False) else "ERR"
                message = entry.get("message", "")
                player = entry.get("player_name")
                if player:
                    print(f"[{ts}] {indicator} {message} - {player}")
                else:
                    print(f"[{ts}] {indicator} {message}")

    else:
        # Nessun comando specificato o "run" esplicito
        if args.command is None:
            logging.getLogger(__name__).info("Nessun comando specificato, avvio in modalità run...")
        main()

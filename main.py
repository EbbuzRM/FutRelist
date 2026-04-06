"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
from __future__ import annotations

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

action_logger = logging.getLogger("actions")


def format_duration(seconds: int) -> str:
    """Formatta i secondi in stringa leggibile (es. '18 min', '1 min 30 s')."""
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} min {s} s" if s > 0 else f"{m} min"
    h, m = divmod(m, 60)
    return f"{h}h {m} min"


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

    # Dedicated actions logger: structured JSON to logs/actions.jsonl
    actions_file_handler = logging.FileHandler(
        log_dir / "actions.jsonl", mode="a", encoding="utf-8"
    )
    actions_file_handler.setLevel(logging.INFO)
    actions_file_handler.setFormatter(JsonFormatter())
    action_logger.setLevel(logging.INFO)
    action_logger.addHandler(actions_file_handler)
    action_logger.propagate = False


def make_status_table(phase: str, scanned: int, relisted: int, errors: int) -> Table:
    current_time = datetime.now().strftime("%H:%M:%S")
    table = Table(title=f"FIFA Auto-Relist [🕒 {current_time}]")
    table.add_column("Fase", style="cyan")
    table.add_column("Scansionati", justify="right")
    table.add_column("Rilistati", justify="right", style="green")
    table.add_column("Errori", justify="right", style="red")
    table.add_row(phase, str(scanned), str(relisted), str(errors))
    return table


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("FIFA_EMAIL")
    password = os.environ.get("FIFA_PASSWORD")

    if email and password:
        return email, password

    raise RuntimeError("Credenziali FIFA_EMAIL o FIFA_PASSWORD non trovate nel file .env")


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
    MAX_CONSOLE_WAIT_HOURS = 4  # aspetta al massimo 4 ore
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
        
        # Facciamo finta che l'esito sia booleano. Se fallisce, verifichiamo il perché.
        success = auth.perform_login(page, email, password)

        if success:
            auth.save_session(controller.context)
            logger.info("Login completato e sessione salvata")
            return
        else:
            # Se ha fallito potremmo aver appena riscoperto la sessione console annidata post-login
            if auth.is_console_session_active(page):
                logger.warning("Rilevata sessione console attiva ORA, in fase di login formale. Riprendo ad attendere...")
                continue # Torna al "while True" e rientra nel "while auth.is_console_session_active"
            
            # Se ha fallito e non è colpa della console... è un errore puro (credenziali o caricamento)
            raise AuthError("Login fallito (non a causa della console)")


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


def get_next_golden_hour(now: datetime) -> datetime | None:
    """Restituisce il prossimo target :10 (16:10, 17:10, 18:10) come datetime.

    Se siamo dopo le 18:10, restituisce None (nessuna golden oggi).
    Se siamo prima delle 16:10, restituisce 16:10.
    Se siamo tra 16:10-17:10, restituisce 17:10.
    Se siamo tra 17:10-18:10, restituisce 18:10.
    """
    golden_targets = [
        now.replace(hour=16, minute=10, second=0, microsecond=0),
        now.replace(hour=17, minute=10, second=0, microsecond=0),
        now.replace(hour=18, minute=10, second=0, microsecond=0),
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
    hour = now.hour
    minute = now.minute
    if hour < 15 or (hour == 15 and minute < 10):
        return False
    if hour > 18 or (hour == 18 and minute > 15):
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

    hour = now.hour
    minute = now.minute
    # Finestra relist: :09-:11 delle ore 16, 17, 18
    if hour in (16, 17, 18) and 9 <= minute <= 11:
        return False  # Momento del relist golden

    return True


def main() -> None:
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")

    controller = None
    app_config = None
    telegram = None

    try:
        cm = ConfigManager()
        app_config = cm.load()
        config = app_config.to_dict()
        logger.info(f"Config caricata (intervallo: {app_config.scan_interval_seconds}s, modalità: {app_config.listing_defaults.relist_mode})")

        from notifier import send_telegram_alert
        send_telegram_alert(app_config.notifications, "✅ FIFA 26 Auto-Relist Tool avviato con successo! Notifiche Telegram attivate.")

        controller = BrowserController(config)
        auth = AuthManager(config)
        
        # Prova a ripristinare il profilo browser esistente
        profile_dir = auth.load_session()
        page = controller.start(user_data_dir=profile_dir)

        controller.navigate_to_webapp()
        logger.info(f"WebApp caricata: {page.title()}")

        authenticate(controller, auth, page)
        logger.info("=== Autenticazione completata ===")

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

        telegram = None
        if app_config.notifications.telegram_token and app_config.notifications.telegram_chat_id:
            telegram = TelegramHandler(
                token=app_config.notifications.telegram_token,
                chat_id=app_config.notifications.telegram_chat_id,
                bot_state=bot_state,
                page=page,
                log_dir=Path(__file__).parent / "logs",
            )
            # Wire SoldHandler for /del_sold command
            sold_handler = SoldHandler(page, config)
            telegram.set_sold_handler(sold_handler)
            telegram.start()
            logger.info("Telegram handler avviato")

        # Notification batching
        last_notification_time = None
        last_relist_error = None
        notification_accumulator = {"relisted": 0, "failed": 0, "cycles": 0}
        NOTIFICATION_INTERVAL = 300  # invia ogni 5 minuti max
        NOTIFICATION_THRESHOLD = 5  # oppure quando >= 5 item accumulati

        logger.info(f"Avvio loop continuo (intervallo: {app_config.scan_interval_seconds}s). Premi Ctrl+C per fermare.")

        status_console = Console()
        
        while True:
            cycle += 1
            logger.info(f"=== Ciclo {cycle} ===")

            # Check if bot is paused via Telegram
            if bot_state.is_paused():
                logger.info("[Telegram] Bot in pausa — skip scanning")
                status_console.print(make_status_table("⏸️ In Pausa (Telegram)", 0, 0, 0))
                time.sleep(10)  # check every 10s if resumed
                continue

            ensure_session(page, auth, controller, get_credentials)

            # Gestione sessione PS5/Console attiva nel loop
            if auth.is_console_session_active(page):
                wait_console = 1800 # 30 minuti
                logger.info(f"Sessione console rilevata. Sospendo per {wait_console}s...")
                status_console.print(make_status_table("Console Attiva", 0, 0, 0))
                time.sleep(wait_console)
                page.reload() # Ricarica per vedere se la sessione è libera
                continue

            # --- HYBRID GOLDEN SYNC LOGIC ---
            now = datetime.now()
            next_golden = get_next_golden_hour(now)
            fifa_logger = logging.getLogger("fifa")

            # Se siamo nella fascia golden, calcola se è ora di navigare o aspettare
            if next_golden and is_in_golden_period(now):
                pre_nav_time = next_golden.replace(minute=9, second=30, microsecond=0)
                seconds_until_golden = (next_golden - now).total_seconds()
                seconds_until_pre_nav = (pre_nav_time - now).total_seconds()

                if seconds_until_pre_nav > 0:
                    # HOLD: aspetta senza navigare fino al pre-nav
                    # Ma fai check della sessione ogni 5 minuti
                    while seconds_until_pre_nav > 0:
                        wait_chunk = min(300, int(seconds_until_pre_nav))  # max 5 min per chunk
                        status_console.print(make_status_table("Pausa Sincro Golden", 0, 0, 0))
                        logger.info(f"[Golden] HOLD: mancano {format_duration(int(seconds_until_golden))} alle {next_golden.strftime('%H:%M')}. Check sessione tra {format_duration(wait_chunk)}.")
                        time.sleep(wait_chunk)

                        # Aggiorna i calcoli dopo il wait
                        now = datetime.now()
                        next_golden = get_next_golden_hour(now)
                        if next_golden is None:
                            break  # Siamo usciti dalla fascia golden
                        pre_nav_time = next_golden.replace(minute=9, second=30, microsecond=0)
                        seconds_until_golden = (next_golden - now).total_seconds()
                        seconds_until_pre_nav = (pre_nav_time - now).total_seconds()

                        # Verifica sessione ad ogni chunk
                        ensure_session(page, auth, controller, get_credentials)

                    if next_golden is None:
                        # Fuori fascia golden, procedi con navigazione normale
                        pass
                    else:
                        # Siamo al pre-nav o oltre — naviga per la golden
                        logger.info("[Golden] PRE-NAV AVVIATA! Navigo ora per arrivare al :10 preciso.")
                elif 0 < seconds_until_golden <= 30:
                    # Timing perfetto: procedi con la navigazione
                    logger.info(f"[Golden] Timing perfetto! Mancano {int(seconds_until_golden)}s al :10, procedo.")
                # else: siamo dopo il :10, naviga normalmente

            if not navigate_with_retry(navigator, page):
                status_console.print(make_status_table("Errore Navigazione", 0, 0, 0))
                rate_limiter.wait()
                continue

            fifa_logger.info(f"--- [SCANSIONE IBRIDA] Minuto {datetime.now().minute}:{datetime.now().second:02d} ---")
            scan = detector.scan_listings()

            succeeded = 0
            failed = 0
            last_relist_error = None
            next_wait = 600  # default fallback

            if scan.expired_count > 0:
                # Se siamo in hold window, NON relistare — aspetta la golden
                in_hold = is_in_hold_window(datetime.now())
                force_relist = bot_state.consume_force_relist()
                if in_hold and not force_relist:
                    next_g = get_next_golden_hour(datetime.now())
                    if next_g:
                        fifa_logger.info(f"[HOLD] {scan.expired_count} scaduti rilevati ma in HOLD WINDOW.")
                        fifa_logger.info(f"[HOLD] Prossima golden: {next_g.strftime('%H:%M')}. Relist rimandato.")
                    succeeded = 0
                    failed = 0
                    next_wait = 60  # check ogni minuto fino alla golden
                elif force_relist:
                    logger.info("[Telegram] Force relist — bypass hold window")
                    # proceed with relist (fall through to normal relist logic)
                    fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti. Rilisto (force)...")
                    if executor.relist_mode == "all":
                        batch = executor.relist_all(count=scan.expired_count)
                        succeeded = batch.succeeded
                        failed = batch.total - batch.succeeded
                        if batch.relist_error:
                            last_relist_error = batch.relist_error
                            fifa_logger.error(f"ERRORE RELIST: {last_relist_error}")
                            if not executor.check_session_valid():
                                fifa_logger.warning("Sessione non valida - tentativo refresh...")
                                page.reload()
                                page.wait_for_timeout(3000)
                                if not executor.check_session_valid():
                                    fifa_logger.warning("Refresh fallito - logout e riavvio")
                                    auth_mgr = AuthManager(config)
                                    auth_mgr.delete_saved_session()
                                    page.goto("https://fcweb2://.ea.com/")
                                    page.wait_for_timeout(3000)
                                    continue
                            screenshot_path = "relist_error.png"
                            page.screenshot(path=screenshot_path)
                    else:
                        expired = [l for l in scan.listings if l.needs_relist]
                        succeeded, failed = relist_expired_listings(executor, expired)

                    fifa_logger.info(f"Relist completato: {succeeded} successi, {failed} falliti.")

                    # Update BotState stats
                    bot_state.update_stats(cycle=cycle, relisted=succeeded, failed=failed)

                    now_after = datetime.now()
                    next_g_after = get_next_golden_hour(now_after)
                    if next_g_after and now_after.minute >= 10 and now_after.minute < 15:
                        # Appena dopo una golden, polling rapido per ritardatari
                        next_wait = random.randint(15, 20)
                        fifa_logger.info(f"Golden Hour: polling rapido per ritardatari in {format_duration(next_wait)}.")
                    else:
                        min_active = get_min_active_seconds(scan)
                        if min_active is not None:
                            next_wait = max(min_active - 20, 10)
                            fifa_logger.info(f"Prossimo expiry tra {format_duration(min_active)}. Wait: {format_duration(next_wait)}")
                        else:
                            # Se siamo in hold window, calcola quanto manca alla golden
                            if is_in_hold_window(now_after):
                                ng = get_next_golden_hour(now_after)
                                if ng:
                                    next_wait = min(60, int((ng.replace(minute=9, second=30) - now_after).total_seconds()))
                                    fifa_logger.info(f"[HOLD] In hold, check tra {format_duration(next_wait)} per golden delle {ng.strftime('%H:%M')}.")
                                else:
                                    next_wait = 3600 - 20
                                    fifa_logger.info(f"Tutti relistati. Wait: {format_duration(next_wait)}")
                            else:
                                next_wait = 3600 - 20
                                fifa_logger.info(f"Tutti relistati. Wait: {format_duration(next_wait)}")
            else:
                fifa_logger.info("Nessun oggetto scaduto trovato.")
                now_ne = datetime.now()
                # Se in hold window, check frequente per la golden
                if is_in_hold_window(now_ne):
                    next_g = get_next_golden_hour(now_ne)
                    if next_g:
                        secs = (next_g.replace(minute=9, second=30) - now_ne).total_seconds()
                        next_wait = min(max(int(secs), 30), 300)  # 30s-5min
                        fifa_logger.info(f"[HOLD] Nessuno scaduto. Prossima golden: {next_g.strftime('%H:%M')}. Check tra {format_duration(next_wait)}.")
                    else:
                        next_wait = 300
                else:
                    min_active = get_min_active_seconds(scan)
                    if min_active is not None:
                        next_wait = max(min_active - 20, 10)
                        fifa_logger.info(f"Prossimo expiry tra {format_duration(min_active)}. Wait: {format_duration(next_wait)}")
                    else:
                        next_wait = 600
                        fifa_logger.info(f"Nessun oggetto in lista. Prossimo check tra {format_duration(next_wait)}.")

            # --- NOTIFICA FINALE UNIFICATA (BATCHING) ---
            if succeeded > 0 or failed > 0:
                logger.info(f"Ciclo completato. Totale: {succeeded} successi, {failed} fallimenti.")

                # Accumula i risultati
                notification_accumulator["relisted"] += succeeded
                notification_accumulator["failed"] += failed
                notification_accumulator["cycles"] += 1

                # Verifica se inviare la notifica
                now = datetime.now()
                time_since_last = (now - last_notification_time).total_seconds() if last_notification_time else float('inf')

                should_notify = (
                    time_since_last >= NOTIFICATION_INTERVAL or
                    notification_accumulator["relisted"] >= NOTIFICATION_THRESHOLD
                )

                if should_notify:
                    if app_config.notifications.telegram_token:
                        from notifier import send_telegram_photo
                        screenshot_path = "relist_report.png"
                        try:
                            page.screenshot(path=screenshot_path)
                            error_msg = f" ⚠️ Error: {last_relist_error}" if last_relist_error else ""
                            msg = (
                                f"🔔 Report Aggregato\n"
                                f"-------------------\n"
                                f"📦 Cicli: {notification_accumulator['cycles']}\n"
                                f"🚀 Totale Rilistati: {notification_accumulator['relisted']}\n"
                                f"❌ Falliti: {notification_accumulator['failed']}{error_msg}\n"
                                f"🕒 Modalità: ⚽ Drift Ibrido"
                            )
                            send_telegram_photo(app_config.notifications, screenshot_path, msg)
                            last_relist_error = None
                            if os.path.exists(screenshot_path):
                                os.remove(screenshot_path)
                        except Exception as e:
                            logger.error(f"Errore invio notifica: {e}")

                    # Reset accumulator
                    notification_accumulator = {"relisted": 0, "failed": 0, "cycles": 0}
                    last_notification_time = now

            # --- CALCOLO ATTESA PER IL PROSSIMO GIRO ---
            logger.info(f"Fine ciclo. In attesa per {format_duration(next_wait)}...")
            rate_limiter.wait()
            time.sleep(next_wait)

    except AuthError as e:
        logger.error(f"Errore autenticazione: {e}")
        if app_config:
            from notifier import send_telegram_alert
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
            from notifier import send_telegram_alert
            send_telegram_alert(app_config.notifications, f"❌ ERRORE CRITICO INATTESO:\n{e}")
        if controller and controller.is_running():
            controller.stop()
        sys.exit(1)


def build_parser():
    """Build CLI argument parser with run and config subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="fifa-relist",
        description="FIFA 26 Auto-Relist Tool",
    )
    sub = parser.add_subparsers(dest="command")

    # run (default)
    sub.add_parser("run", help="Start the auto-relist tool")

    # config
    config_parser = sub.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_action")

    config_sub.add_parser("show", help="Display current settings")

    set_parser = config_sub.add_parser("set", help="Update a setting")
    set_parser.add_argument("key", help="Dotted key (e.g., listing_defaults.duration)")
    set_parser.add_argument("value", help="New value")

    config_sub.add_parser("reset", help="Reset all settings to defaults")

    # history
    history_parser = sub.add_parser("history", help="Mostra cronologia azioni")
    history_parser.add_argument(
        "-n", "--lines", type=int, default=20, help="Numero di voci da mostrare"
    )

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "config":
        from config.config import ConfigManager

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
                success = entry.get("success", False)
                indicator = "OK" if success else "ERR"
                message = entry.get("message", "")
                player = entry.get("player_name")
                if player:
                    print(f"[{ts}] {indicator} {message} - {player}")
                else:
                    print(f"[{ts}] {indicator} {message}")
    else:
        main()

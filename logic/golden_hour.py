from __future__ import annotations
from datetime import datetime
import logging
from models.listing import ListingState, ListingScanResult

# ---------------------------------------------------------------------------
# Costanti Golden Hour — unica fonte di verità
# ---------------------------------------------------------------------------
GOLDEN_HOURS: tuple[int, ...] = (16, 17, 18)
GOLDEN_MINUTE: int = 10          # :10 di ogni golden hour
GOLDEN_PRE_NAV_MINUTE: int = 9   # navigazione pre-golden a :09:00
GOLDEN_RELIST_WINDOW: range = range(9, 12)   # :09 → :11 inclusi
GOLDEN_CLOSE_WINDOW: range = range(8, 13)    # :08 → :12 "vicino alla golden"
GOLDEN_PERIOD_START: tuple[int, int] = (15, 10)  # 15:10
GOLDEN_PERIOD_END: tuple[int, int] = (18, 15)    # 18:15

# ---------------------------------------------------------------------------
# Costanti Processing Items Fuori Golden Window
# ---------------------------------------------------------------------------
PROCESSING_MAX_ATTEMPTS: int = 15           # Tentativi massimi per processing items
PROCESSING_MIN_WAIT: int = 30               # Attesa minima in secondi
PROCESSING_MAX_WAIT: int = 60               # Attesa massima in secondi
PROCESSING_MAX_TOTAL_TIME: int = 300        # Timeout massimo totale (5 minuti)

logger = logging.getLogger(__name__)

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
    """Restituisce la PROSSIMA golden hour futura (16:10, 17:10, 18:10) come datetime.
    
    La funzione restituisce SEMPRE una golden hour nel futuro, mai quella corrente
    anche se siamo nella sua finestra di rilist (:09-:11).
    Se non ci sono più golden hours oggi, restituisce None.
    """
    for target_hour in sorted(GOLDEN_HOURS):
        target = now.replace(hour=target_hour, minute=GOLDEN_MINUTE, second=0, microsecond=0)
        
        # MUST be strictly in the future
        if target > now:
            return target
    
    return None  # No more golden hours today

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

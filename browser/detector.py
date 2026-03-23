"""DOM detector for transfer market listings.

Reads listing state from the page after navigator reaches Transfer List view.
Handles empty state, player data extraction, state mapping, price/rating parsing.
"""
import re
import logging
from playwright.sync_api import Page
from models.listing import ListingState, PlayerListing, ListingScanResult

logger = logging.getLogger(__name__)

SELECTORS = {
    "listing_items": '.listFUTItem.player',
    "listing_container": '.ut-transfer-list-view',
    "player_name": '.player-name, .name',
    "player_rating": '.rating, .player-rating',
    "player_position": '.position',
    "auction_state": '.auction-state',
    "auction_price": '.auctionValue, .auction-value',
    "auction_start_price": '.auctionStartPrice',
    "expired_marker": '.expired, .auction-state-expired',
    "active_marker": '.active, .auction-state-active',
    "sold_marker": '.sold',
    "relist_button": 'button:has-text("Relist"), .relist-btn',
    "empty_state": '.no-items, .empty-list, .no-listings',
    "time_remaining": '.time-remaining, .auction-time',
}


def parse_price(text: str | None) -> int | None:
    """Parse a price string like '10,000 coins' into an integer.

    Examples:
        '10,000 coins' -> 10000
        '500' -> 500
        None -> None
    """
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    if digits:
        return int(digits)
    return None


def parse_rating(text: str | None) -> int | None:
    """Parse a rating string like 'OVR 91' or '87' into an integer.

    Examples:
        '87' -> 87
        'OVR 91' -> 91
        None -> None
    """
    if not text:
        return None
    match = re.search(r'\d+', text)
    if match:
        return int(match.group())
    return None


def determine_state(state_text: str) -> ListingState:
    """Map auction state text to ListingState enum.

    Supports Italian and English keywords.
    """
    if not state_text:
        return ListingState.UNKNOWN

    text = state_text.lower().strip()

    if any(kw in text for kw in ("expired", "scadut", "expir")):
        return ListingState.EXPIRED
    if any(kw in text for kw in ("active", "attiv", "selling", "vendita")):
        return ListingState.ACTIVE
    if any(kw in text for kw in ("sold", "vendut", "completed")):
        return ListingState.SOLD

    logger.warning(f"Stato listing non riconosciuto: '{state_text}'")
    return ListingState.UNKNOWN


class ListingDetector:
    """Rileva e legge i listing dal DOM del Transfer Market."""

    def __init__(self, page: Page):
        self.page = page

    def scan_listings(self) -> ListingScanResult:
        """Scansiona tutti i listing e restituisce un ListingScanResult."""
        # Step 1: check for empty state
        empty_el = self.page.query_selector(SELECTORS["empty_state"])
        if empty_el:
            logger.info("Nessun listing trovato (stato vuoto rilevato)")
            return ListingScanResult.empty()

        items = self.page.query_selector_all(SELECTORS["listing_items"])
        if not items:
            logger.info("Nessun listing trovato (nessun elemento nella pagina)")
            return ListingScanResult.empty()

        # Step 2: bulk extract with eval_on_selector_all
        try:
            raw_listings = self.page.eval_on_selector_all(
                SELECTORS["listing_items"],
                """els => els.map(el => {
                    const nameEl = el.querySelector('.player-name, .name');
                    const ratingEl = el.querySelector('.rating, .player-rating');
                    const posEl = el.querySelector('.position');
                    const stateEl = el.querySelector('.auction-state');
                    const priceEl = el.querySelector('.auctionValue, .auction-value');
                    const startPriceEl = el.querySelector('.auctionStartPrice');
                    const timeEl = el.querySelector('.time-remaining, .auction-time');
                    return {
                        name: nameEl ? nameEl.textContent.trim() : '',
                        rating: ratingEl ? ratingEl.textContent.trim() : '',
                        position: posEl ? posEl.textContent.trim() : '',
                        state: stateEl ? stateEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim() : '',
                        startPrice: startPriceEl ? startPriceEl.textContent.trim() : '',
                        time: timeEl ? timeEl.textContent.trim() : '',
                    };
                })"""
            )
        except Exception as e:
            logger.warning(f"Fallita estrazione bulk, uso fallback per-elemento: {e}")
            raw_listings = []
            for el in items:
                raw = self._extract_single_listing(el)
                if raw:
                    raw_listings.append(raw)

        # Step 3: convert to PlayerListing objects
        listings: list[PlayerListing] = []
        for i, raw in enumerate(raw_listings):
            listing = PlayerListing(
                index=i,
                player_name=raw.get("name", ""),
                rating=parse_rating(raw.get("rating")),
                position=raw.get("position") or None,
                state=determine_state(raw.get("state", "")),
                current_price=parse_price(raw.get("price")),
                start_price=parse_price(raw.get("startPrice")),
                time_remaining=raw.get("time") or None,
            )
            listings.append(listing)

        # Step 4: build scan result
        active_count = sum(1 for l in listings if l.state == ListingState.ACTIVE)
        expired_count = sum(1 for l in listings if l.state == ListingState.EXPIRED)
        sold_count = sum(1 for l in listings if l.state == ListingState.SOLD)

        result = ListingScanResult(
            total_count=len(listings),
            active_count=active_count,
            expired_count=expired_count,
            sold_count=sold_count,
            listings=listings,
        )

        logger.info(
            f"Scansione completata: {result.total_count} listing "
            f"({active_count} attivi, {expired_count} scaduti, {sold_count} venduti)"
        )
        return result

    def _extract_single_listing(self, element) -> dict | None:
        """Fallback: estrae un singolo listing per-elemento quando bulk fallisce."""
        try:
            def _text(sel: str) -> str:
                el = element.query_selector(sel)
                return el.text_content().strip() if el else ""

            return {
                "name": _text(SELECTORS["player_name"]),
                "rating": _text(SELECTORS["player_rating"]),
                "position": _text(SELECTORS["player_position"]),
                "state": _text(SELECTORS["auction_state"]),
                "price": _text(SELECTORS["auction_price"]),
                "startPrice": _text(SELECTORS["auction_start_price"]),
                "time": _text(SELECTORS["time_remaining"]),
            }
        except Exception as e:
            logger.warning(f"Errore estrazione singolo listing: {e}")
            return None

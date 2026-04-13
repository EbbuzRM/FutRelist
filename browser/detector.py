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
    "listing_items": '.listFUTItem',
    "player_name": '.player-name, .name, .ut-item-player-name',
    "player_rating": '.rating, .player-rating, .ut-item-player-rating',
    "player_position": '.position',
    "auction_state": '.time, .auction-state-value, .auction-state',
    "auction_price": '.auctionValue, .auction-value',
    "auction_start_price": '.auctionStartPrice',
    "empty_state": '.no-items, .empty-list, .no-listings',
    "time_remaining": '.time-remaining, .auction-time, .time',
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


def parse_time_remaining(text: str | None) -> int | None:
    """Parse time string into total seconds.

    Handles multiple formats:
      - EA WebApp colon format: '59:28' (MM:SS), '1:05:30' (H:MM:SS)
      - Letter suffix format:   '1h 5m', '45m', '30s'

    Returns None if 'Expired', empty, or unparsable.
    """
    if not text or "expir" in text.lower() or "scadut" in text.lower():
        return None

    t = text.strip().lower()

    # --- Formato EA '<N Seconds', '<N Minutes', '<N Hours' ---
    # Es: '<15 Seconds' → 15s, '<5 Seconds' → 5s, '<1 Minutes' → 60s
    lt_match = re.match(r'<\s*(\d+)\s*(second|sec|minut|min|hour|h)', t)
    if lt_match:
        n = int(lt_match.group(1))
        unit = lt_match.group(2)
        if unit.startswith('second') or unit == 'sec':
            return n
        elif unit.startswith('minut') or unit == 'min':
            return n * 60
        elif unit.startswith('hour') or unit == 'h':
            return n * 3600

    # --- Formato H:MM:SS o MM:SS (usato dalla EA WebApp) ---
    colon_match = re.fullmatch(r'(\d+):(\d{2}):(\d{2})', t)
    if colon_match:
        h, m, s = int(colon_match.group(1)), int(colon_match.group(2)), int(colon_match.group(3))
        return h * 3600 + m * 60 + s

    colon_match2 = re.fullmatch(r'(\d+):(\d{2})', t)
    if colon_match2:
        m, s = int(colon_match2.group(1)), int(colon_match2.group(2))
        return m * 60 + s

    # --- Formato EA a parola intera: '59 Minutes', '5 Seconds', '2 Hours' ---
    # (distinto dal suffisso compatto '45m' che non ha spazio)
    word_match = re.match(r'(\d+)\s+(second|minut|hour)\w*', t)
    if word_match:
        n = int(word_match.group(1))
        unit = word_match.group(2)
        if unit.startswith('second'):
            return n
        elif unit.startswith('minut'):
            return n * 60
        elif unit.startswith('hour'):
            return n * 3600

    # --- Formato con suffisso compatto: '1h 5m', '45m', '30s' ---
    total_seconds = 0
    h_match = re.search(r'(\d+)h', t)
    if h_match:
        total_seconds += int(h_match.group(1)) * 3600
    m_match = re.search(r'(\d+)m', t)
    if m_match:
        total_seconds += int(m_match.group(1)) * 60
    s_match = re.search(r'(\d+)s', t)
    if s_match:
        total_seconds += int(s_match.group(1))

    return total_seconds if total_seconds > 0 else None


def determine_state(state_text: str) -> ListingState:
    """Map auction state text to ListingState enum.

    Supports Italian and English keywords.
    """
    if not state_text:
        return ListingState.UNKNOWN

    text = state_text.lower().strip()

    if any(kw in text for kw in ("sold", "vendut", "completed")):
        return ListingState.SOLD
    if any(kw in text for kw in ("expired", "scadut", "expir")):
        return ListingState.EXPIRED
    # Processing... = item in limbo EA: scaduti ma non ancora visibili come "Expired".
    # EA li lascia temporaneamente nella sezione "active" del DOM con questo testo.
    if any(kw in text for kw in ("processing", "elaborazion")):
        return ListingState.PROCESSING
    if any(kw in text for kw in ("active", "attiv", "selling", "vendita", "minut", "hour", "ora", "second", "<", "m ", "h ", "s ")):
        return ListingState.ACTIVE

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

        # Step 2: determina la sezione di appartenenza di ogni item per posizione.
        # La WebApp EA ha struttura flat: heading (h2/h3) e lista item sono fratelli,
        # non genitori/figli. Leggiamo tutti i nodi h2/h3 e tutti i .listFUTItem
        # nell'ordine in cui compaiono nel DOM, poi assegniamo la sezione per posizione.
        try:
            section_by_index: list[str] = self.page.evaluate(
                """() => {
                    // Raccoglie tutti i nodi h2/h3 E tutti gli item nel DOM, in ordine
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_ELEMENT,
                        {
                            acceptNode(node) {
                                const tag = node.tagName;
                                if ((tag === 'H2' || tag === 'H3') || node.classList.contains('listFUTItem'))
                                    return NodeFilter.FILTER_ACCEPT;
                                return NodeFilter.FILTER_SKIP;
                            }
                        }
                    );
                    let currentSection = '';
                    const sections = [];
                    let node;
                    while ((node = walker.nextNode())) {
                        const tag = node.tagName;
                        if (tag === 'H2' || tag === 'H3') {
                            const t = node.textContent.toLowerCase();
                            // IMPORTANTE: "unsold" contiene "sold" → controllare unsold/expired PRIMA
                            if (t.includes('unsold') || t.includes('expired') || t.includes('scadut')) currentSection = 'expired';
                            else if (t.includes('sold') || t.includes('vendut')) currentSection = 'sold';
                            else if (t.includes('active') || t.includes('attiv') || t.includes('available')) currentSection = 'active';
                        } else {
                            sections.push(currentSection);
                        }
                    }
                    return sections;
                }"""
            )
        except Exception as e:
            logger.warning(f"Impossibile determinare sezioni per posizione: {e}")
            section_by_index = [""] * len(items)

        # Step 3: bulk extract item data
        try:
            raw_listings = self.page.eval_on_selector_all(
                SELECTORS["listing_items"],
                """els => els.map(el => {
                    const nameEl = el.querySelector('.player-name, .name, .ut-item-player-name');
                    const ratingEl = el.querySelector('.rating, .player-rating, .ut-item-player-rating');
                    const posEl = el.querySelector('.position');

                    // Cerca lo stato provando vari selettori in ordine di affidabilità
                    let state = '';
                    const stateSelectors = ['.time', '.auction-state-value', '.auction-state'];
                    for (const sel of stateSelectors) {
                        const found = el.querySelector(sel);
                        if (found) {
                            const val = found.textContent.trim();
                            if (val && val.length > 1 && val !== '---') {
                                state = val;
                                break;
                            }
                        }
                    }

                    const priceEl = el.querySelector('.auctionValue, .auction-value');
                    const startPriceEl = el.querySelector('.auctionStartPrice');
                    const timeEl = el.querySelector('.time-remaining, .auction-time, .time');
                    return {
                        name: nameEl ? nameEl.textContent.trim() : '',
                        rating: ratingEl ? ratingEl.textContent.trim() : '',
                        position: posEl ? posEl.textContent.trim() : '',
                        state: state,
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

        # Step 4: convert to PlayerListing objects
        listings: list[PlayerListing] = []
        for i, raw in enumerate(raw_listings):
            state_text = raw.get("state", "")
            section = section_by_index[i] if i < len(section_by_index) else ""
            # Se section_by_index non ha info (bulk fallita, fallback usato),
            # prova a usare la sezione estratta direttamente dal fallback per-elemento
            if not section:
                section = raw.get("section", "")

            logger.debug(
                f"  [item {i}] name={raw.get('name')!r} "
                f"state_text={state_text!r} section={section!r} time={raw.get('time')!r}"
            )

            # La sezione rilevata per posizione è la fonte più affidabile,
            # ECCEZIONE: "Processing..." appare nella sezione 'active' del DOM
            # ma non è un listing attivo — è in limbo post-scadenza lato EA.
            # Il testo del timer ha priorità sulla sezione in questo caso specifico.
            state_text_lower = state_text.lower()
            is_processing = any(kw in state_text_lower for kw in ("processing", "elaborazion"))

            if section == "sold":
                state = ListingState.SOLD
            elif section == "expired":
                state = ListingState.EXPIRED
            elif section == "active" and is_processing:
                # Override: EA mette i Processing... in sezione active, ma vanno trattati
                # come PROCESSING (da relistare), non come ACTIVE (timer valido).
                state = ListingState.PROCESSING
            elif section == "active":
                state = ListingState.ACTIVE
            else:
                # Fallback: prova a determinare lo stato dal testo del timer
                state = determine_state(state_text)

            listing = PlayerListing(
                index=i,
                player_name=raw.get("name", ""),
                rating=parse_rating(raw.get("rating")),
                position=raw.get("position") or None,
                state=state,
                current_price=parse_price(raw.get("price")),
                start_price=parse_price(raw.get("startPrice")),
                time_remaining=raw.get("time") or None,
                time_remaining_seconds=parse_time_remaining(raw.get("time")),
            )
            listings.append(listing)

        # Step 5: build scan result
        active_count = sum(1 for l in listings if l.state == ListingState.ACTIVE)
        expired_count = sum(
            1 for l in listings
            if l.state in (ListingState.EXPIRED, ListingState.PROCESSING)
        )
        sold_count = sum(1 for l in listings if l.state == ListingState.SOLD)
        processing_count = sum(1 for l in listings if l.state == ListingState.PROCESSING)

        result = ListingScanResult(
            total_count=len(listings),
            active_count=active_count,
            expired_count=expired_count,
            sold_count=sold_count,
            listings=listings,
        )

        processing_log = f" (di cui {processing_count} in processing)" if processing_count > 0 else ""
        logger.info(
            f"Scansione completata: {result.total_count} listing "
            f"({active_count} attivi, {expired_count} scaduti{processing_log}, {sold_count} venduti)"
        )
        return result

    def _extract_single_listing(self, element) -> dict | None:
        """Fallback: estrae un singolo listing per-elemento quando bulk fallisce."""
        try:
            def _text(sel: str) -> str:
                el = element.query_selector(sel)
                # text_content() è il metodo Python corretto (non el.textContent che è JS)
                return (el.text_content() or "").strip() if el else ""

            # Cerca l'heading precedente risalendo i sibling e poi il parent,
            # tramite evaluate() che esegue JS nel contesto del nodo reale.
            # Nota: il DOM EA è flat (heading e item-list sono fratelli), quindi
            # element.parent_element non funzionerebbe (non è API Playwright Python,
            # e anche concettualmente si cercherebbe nel container sbagliato).
            try:
                section = element.evaluate("""el => {
                    function findPrecedingHeading(node) {
                        let cur = node.previousElementSibling;
                        while (cur) {
                            const tag = cur.tagName;
                            if (tag === 'H2' || tag === 'H3') return cur.textContent.toLowerCase();
                            cur = cur.previousElementSibling;
                        }
                        if (node.parentElement) return findPrecedingHeading(node.parentElement);
                        return '';
                    }
                    const t = findPrecedingHeading(el);
                    if (t.includes('unsold') || t.includes('expired') || t.includes('scadut')) return 'expired';
                    if (t.includes('sold') || t.includes('vendut')) return 'sold';
                    if (t.includes('active') || t.includes('attiv') || t.includes('available')) return 'active';
                    return '';
                }""")
            except Exception:
                section = ""

            return {
                "name": _text(SELECTORS["player_name"]),
                "rating": _text(SELECTORS["player_rating"]),
                "position": _text(SELECTORS["player_position"]),
                "state": _text(SELECTORS["auction_state"]),
                "section": section,
                "price": _text(SELECTORS["auction_price"]),
                "startPrice": _text(SELECTORS["auction_start_price"]),
                "time": _text(SELECTORS["time_remaining"]),
            }
        except Exception as e:
            logger.warning(f"Errore estrazione singolo listing: {e}")
            return None

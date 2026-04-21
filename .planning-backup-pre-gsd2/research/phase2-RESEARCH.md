# Phase 2: Transfer Market Navigation — Research

**Researched:** 2026-03-23
**Domain:** FIFA/EA FC WebApp browser automation — Transfer List scraping
**Confidence:** MEDIUM-HIGH

---

## Summary

Phase 2 navigates the FIFA/EA FC 26 WebApp to the Transfer List (My Listings) and reads listing state. The WebApp is a Single Page Application (SPA) built with JavaScript. Player listings are rendered dynamically via internal controllers. Existing community tools (EasyFUT, fut-trade-enhancer, FUT Trade Enhancer, RelistingBot) provide reference CSS selectors and DOM patterns that have been stable across multiple FIFA/FC versions (FIFA 21 through FC 26).

**Key challenge:** CSS selectors are **not officially documented by EA** — they are reverse-engineered by the community and may change between WebApp updates. The architecture must be resilient to selector changes.

**Primary recommendation:** Build a `TransferMarketNavigator` class in `browser/navigator.py` with a `ListingDetector` class in `browser/detector.py`. Use CSS selectors from verified community tools, but centralize them in a `SELECTORS` dict (like `auth.py` already does) so they can be updated without touching logic.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `playwright` | >= 1.40.0 | Browser automation, DOM querying | Already in project; sync API used throughout |
| `playwright.sync_api.Page` | — | Page interaction, element querying | Core abstraction for all browser ops |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` | stdlib | Structured data for listings | Represent player listing data |
| `logging` | stdlib | Debug/trace logging | Already used in project |
| `re` | stdlib | Regex for text parsing | Extract rating/price from mixed text |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `playwright.sync_api` | `playwright.async_api` | Async is more performant but inconsistent with existing codebase (all sync) |
| CSS selectors | `page.evaluate()` JS injection | JS injection is more fragile; CSS selectors are more maintainable |
| DOM scraping | FUT internal API interception | API interception gives raw data but requires reverse-engineering network calls; DOM is more stable |

**No new pip dependencies required** — `playwright` already in `requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure (Phase 2 additions)

```
fifa-relist/
├── browser/
│   ├── __init__.py
│   ├── controller.py          # EXISTS — browser lifecycle
│   ├── auth.py                # EXISTS — login + session
│   ├── navigator.py           # NEW — Transfer Market navigation
│   └── detector.py            # NEW — listing state detection
├── models/
│   ├── __init__.py            # NEW
│   └── listing.py             # NEW — Listing data class
├── main.py                    # MODIFIED — integrate Phase 2
├── config/
│   └── config.json            # EXISTS — may add navigator config
```

### Pattern 1: Navigator + Detector Separation

**What:** Separate "navigation" (clicking through menus to reach Transfer List) from "detection" (reading listing state from the DOM). Navigator handles page transitions; Detector handles data extraction.

**When to use:** Always when the WebApp has multi-step navigation before data extraction.

**Why:** Navigation is flaky (loading states, animations) and needs retry logic. Detection is data-focused and needs parsing logic. Separating them makes each independently testable and retryable.

```
BrowserController (lifecycle)
    └── AuthManager (login)
        └── TransferMarketNavigator (navigate to My Listings)
            └── ListingDetector (read listings from DOM)
```

### Pattern 2: CSS Selector Centralization

**What:** All CSS selectors live in a single `SELECTORS` dict at the top of each module (like `auth.py` already does). This is the proven pattern from community tools.

**When to use:** Always. EA updates the WebApp periodically; centralized selectors minimize change impact.

**Example structure:**
```python
# browser/navigator.py
SELECTORS = {
    "transfers_nav": 'button:has-text("Transfers"), .icon-transfer',
    "transfer_list_tab": 'button:has-text("Transfer List"), .ut-tile-transfer-list',
    "my_listings_view": '.ut-transfer-list-view, .sectioned-item-list',
    "loading_indicator": '.ut-loading-spinner, .loading',
}

# browser/detector.py
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
```

### Pattern 3: Wait-for-Ready Before Extraction

**What:** Before reading any data, wait for the listing container to be visible and stable. Use `wait_for_selector` with `networkidle` for page transitions.

**When to use:** Every time you navigate to a new view in the WebApp.

**Example:**
```python
# Source: Playwright docs + community patterns
# Navigate and wait for listing view
page.click(SELECTORS["transfer_list_tab"])
page.wait_for_load_state("networkidle", timeout=15000)
page.wait_for_selector(SELECTORS["listing_container"], state="visible", timeout=10000)
```

### Anti-Patterns to Avoid

- **Hard-coded sleep (`time.sleep`)**: Use Playwright's built-in waits (`wait_for_selector`, `wait_for_load_state`). The WebApp loading time varies; fixed sleeps are either too short (race condition) or too long (slow tool).
- **Single-selector extraction**: Don't rely on one CSS selector for all data. Use multiple selectors with fallbacks (e.g., try `.player-name` first, then `.name`).
- **Assuming English locale**: The WebApp may show text in Italian/other languages. Use CSS class-based selectors, not text-based (`has-text`), for data extraction. Text-based is OK for navigation buttons.
- **Not handling empty state**: Always check for "no listings" before trying to read listing items.

---

## CSS Selectors for EA FC WebApp (My Listings)

### Confidence: MEDIUM — Based on community tools, not official EA docs

Selectors are derived from:
- `fut23tamperScript.js` (hearimm) — verified `.listFUTItem.player`, `.ut-transfer-list-view`
- `fut-trade-enhancer` (ckalgos) — verified autolist and transfer list patterns
- `EasyFUT` (Kava4) — verified auto-relist feature
- `FSU EAFC FUT WEB Enhancer` (futcd_kcka) — verified FC 26 compatible (version 26.05)
- FUT WebApp guides (FIFAUTeam, FUTFC.gg) — navigation flow verification

### Navigation Path
```
WebApp Home → Left Sidebar "Transfers" → "Transfer List" tab
```

The "Transfer List" contains all your active/expired/sold listings.

### Container & Item Selectors
| Element | CSS Selector | Source |
|---------|-------------|--------|
| Transfer List view | `.ut-transfer-list-view` | fut23tamperScript.js |
| Listing item (player) | `.listFUTItem.player` | fut23tamperScript.js |
| Listing item (auction) | `.listFUTItem.auction` | fut23tamperScript.js |
| Sectioned item list | `.sectioned-item-list` | fut23tamperScript.js |

### Player Data Selectors (within each `.listFUTItem`)
| Data | CSS Selector | Notes |
|------|-------------|-------|
| Player name | `.player-name` or nested text in `.name` | May vary by item type |
| Rating | `.rating` | Numeric, e.g., "87" |
| Position | `.position` | E.g., "ST", "CAM" |
| Auction state | `.auction-state` | Text: "Active", "Expired", "Sold" |
| Current price | `.auctionValue` | Buy Now price |
| Starting price | `.auctionStartPrice` | Starting bid |
| Time remaining | `.time-remaining` | For active listings |

### State Indicators
| State | Detection Strategy | Source |
|-------|-------------------|--------|
| **Active** | `.auction-state` contains "Active" OR time remaining > 0 | Community tools pattern |
| **Expired** | `.auction-state` contains "Expired" OR `.listFUTItem` has `expired` class | Community tools pattern |
| **Sold** | `.auction-state` contains "Sold" | Community tools pattern |
| **Empty (no listings)** | No `.listFUTItem` elements found OR `.no-items` message visible | Detection logic |

### Relist Button
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Relist button | `button:has-text("Relist")` | Appears on expired items only |

### Internal API Access (Alternative — HIGH risk)
Some community tools access the WebApp's internal JavaScript objects:
```javascript
// Getting listing data from internal controller (UNSTABLE)
getCurrentController()._listController._view._list.listRows
```
**Risk level: HIGH** — Internal APIs change between versions. CSS selectors are safer.

---

## Data Model

### Listing Data Class

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ListingState(Enum):
    ACTIVE = "active"       # Currently on transfer market
    EXPIRED = "expired"     # Didn't sell, needs relist
    SOLD = "sold"           # Successfully sold
    UNKNOWN = "unknown"     # Could not determine state

@dataclass
class PlayerListing:
    """Represents a single player listing on the Transfer List."""
    index: int                      # Position in the list (0-based)
    player_name: str                # Player name (e.g., "Mbappé")
    rating: Optional[int]           # Overall rating (e.g., 91)
    position: Optional[str]         # Position (e.g., "ST")
    state: ListingState             # Active/Expired/Sold/Unknown
    current_price: Optional[int]    # Current listing price (coins)
    start_price: Optional[int]      # Starting bid price (coins)
    time_remaining: Optional[str]   # Time remaining (active only)
    
    @property
    def needs_relist(self) -> bool:
        return self.state == ListingState.EXPIRED
```

### Detection Result

```python
@dataclass
class ListingScanResult:
    """Result of a full Transfer List scan."""
    total_items: int
    active_count: int
    expired_count: int
    sold_count: int
    listings: list[PlayerListing]
    is_empty: bool
    
    @classmethod
    def empty(cls) -> "ListingScanResult":
        return cls(
            total_items=0, active_count=0,
            expired_count=0, sold_count=0,
            listings=[], is_empty=True
        )
```

---

## Detection Strategy

### Flow: Reading Transfer List State

```
1. Navigate to Transfer List
   └── Wait for .ut-transfer-list-view to be visible
   
2. Check for empty state
   ├── If no .listFUTItem elements → return ListingScanResult.empty()
   └── If .no-items message visible → return ListingScanResult.empty()
   
3. Extract all listing items
   └── page.query_selector_all('.listFUTItem')
   
4. For each listing item:
   ├── Extract player name from .player-name
   ├── Extract rating from .rating
   ├── Extract position from .position  
   ├── Determine state from .auction-state text
   │   ├── "Expired" → ListingState.EXPIRED
   │   ├── "Active" → ListingState.ACTIVE
   │   ├── "Sold" → ListingState.SOLD
   │   └── else → ListingState.UNKNOWN
   ├── Extract prices from .auctionValue, .auctionStartPrice
   └── Parse prices to int (remove "coins" text, commas)
   
5. Build ListingScanResult with counts and listings
```

### Price Parsing

Prices in the WebApp are displayed as formatted strings: "10,000 coins" or "10,000". Need to:
1. Extract text from price element
2. Remove non-numeric characters (except commas for thousand separators)
3. Remove commas
4. Convert to `int`
5. Handle `None`/empty gracefully

```python
import re

def parse_price(text: str | None) -> int | None:
    """Parse '10,000 coins' → 10000"""
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None
```

### Rating Parsing

Rating is typically a simple number in a span: "87". Parse to `int`, handle `None`.

```python
def parse_rating(text: str | None) -> int | None:
    """Parse '87' → 87"""
    if not text:
        return None
    match = re.search(r'\d+', text)
    return int(match.group()) if match else None
```

---

## Dependencies from Phase 1

| Phase 1 Component | Phase 2 Usage | Integration Point |
|-------------------|---------------|-------------------|
| `BrowserController.get_page()` | Get Page object for navigation | `page = controller.get_page()` |
| `BrowserController.is_running()` | Verify browser is active | Pre-flight check |
| `AuthManager.is_logged_in()` | Verify session before navigation | Pre-flight check |
| `SELECTORS["transfer_market"]` | Navigate to Transfer Market | Existing selector in auth.py |
| `SELECTORS["my_listings"]` | Navigate to My Listings | Existing selector in auth.py |
| `config.json` | Read rate_limiting delays | Between actions |

### Integration in main.py

```python
# After successful login in main.py:
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector

navigator = TransferMarketNavigator(page, config)
detector = ListingDetector(page)

navigator.go_to_transfer_list()
result = detector.scan_listings()

if result.is_empty:
    logger.info("Nessun listing trovato")
elif result.expired_count > 0:
    logger.info(f"Trovati {result.expired_count} listing scaduti")
    # Phase 3 will handle relisting
```

---

## Rate Limiting & Safety

### Config Fields Already Available
- `rate_limiting.min_delay_ms`: 2000 (minimum delay between actions)
- `rate_limiting.max_delay_ms`: 5000 (maximum delay between actions)

### Required Delays
| Action | Delay | Reason |
|--------|-------|--------|
| After clicking "Transfers" | 2-3s | Page transition animation |
| After clicking "Transfer List" | 2-3s | Content loading |
| Between reading listings | 500ms-1s | Avoid appearing like a bot |
| After any failed detection | 5-10s | Recovery backoff |

### Bot Detection Risks (MEDIUM)
EA has automated bot detection on the WebApp:
- **Soft ban**: Temporary market access restriction (hours to days)
- **CAPTCHA**: May appear if actions are too fast/automated
- **Rate limiting**: Market searches return empty results

**Mitigation**: Use `slow_mo: 500` from config (already set), add random delays, don't scan more than once per `scan_interval_seconds` (60s default).

---

## Common Pitfalls

### Pitfall 1: Selector Breakage After WebApp Update
**What goes wrong:** EA updates the WebApp, CSS class names change, all selectors fail.
**Why it happens:** WebApp is a JS SPA; class names are not stable API.
**How to avoid:** 
- Centralize selectors in one dict (easy to update)
- Add multiple fallback selectors per element
- Log selector failures with page screenshot for debugging
- Check `page.content()` when selectors fail to see current DOM

**Warning signs:** All listings return empty, console shows "element not found" repeatedly.

### Pitfall 2: Race Condition on Page Load
**What goes wrong:** Try to read listings before the page has fully loaded them.
**Why it happens:** SPA loads content asynchronously; DOM exists but data isn't populated yet.
**How to avoid:** Always `wait_for_selector` on the container before reading items. Use `wait_for_load_state("networkidle")` after navigation.
**Warning signs:** Intermittent empty results, inconsistent player names.

### Pitfall 3: Locale-Dependent Text Matching
**What goes wrong:** Checking `if "Expired" in state_text` fails on Italian/German WebApp.
**Why it happens:** WebApp text is localized; "Scaduto" ≠ "Expired".
**How to avoid:** Use CSS class-based detection where possible. If text-based, check multiple languages or use the Italian config this project already uses.
**Warning signs:** Listings stuck as "Unknown" state.

### Pitfall 4: Sold Items Blocking Scan
**What goes wrong:** Sold items on the list cause parsing errors or confuse the expired/active detection.
**Why it happens:** Sold items have different DOM structure (no time remaining, different button).
**How to avoid:** Detect "Sold" state first, skip sold items from relist consideration, handle separately.
**Warning signs:** Crashes on `parse_price` or `parse_rating` with None values.

---

## Code Examples

### Example 1: Navigate to Transfer List
```python
# Source: Playwright docs + auth.py patterns
def go_to_transfer_list(page: Page) -> bool:
    """Navigate to Transfer Market > Transfer List."""
    try:
        # Click Transfers in sidebar
        transfers_btn = page.query_selector(SELECTORS["transfers_nav"])
        if not transfers_btn:
            logger.error("Pulsante Transfers non trovato")
            return False
        transfers_btn.click()
        page.wait_for_timeout(2000)
        
        # Click Transfer List tab
        list_btn = page.query_selector(SELECTORS["transfer_list_tab"])
        if not list_btn:
            logger.error("Pulsante Transfer List non trovato")
            return False
        list_btn.click()
        
        # Wait for listing view to load
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_selector(
            SELECTORS["listing_container"], 
            state="visible", 
            timeout=10000
        )
        return True
    except Exception as e:
        logger.error(f"Errore navigazione: {e}")
        return False
```

### Example 2: Extract Listing Data
```python
# Source: Playwright eval_on_selector_all + community patterns
def extract_listings(page: Page) -> list[dict]:
    """Extract all listing items from the Transfer List."""
    # Check for empty state first
    items = page.query_selector_all(SELECTORS["listing_items"])
    if not items:
        logger.info("Nessun listing trovato (lista vuota)")
        return []
    
    # Bulk extract using eval_on_selector_all (more efficient)
    raw_listings = page.eval_on_selector_all(
        SELECTORS["listing_items"],
        """items => items.map(item => {
            const name = item.querySelector('.player-name')?.textContent?.trim() || '';
            const rating = item.querySelector('.rating')?.textContent?.trim() || '';
            const position = item.querySelector('.position')?.textContent?.trim() || '';
            const state = item.querySelector('.auction-state')?.textContent?.trim() || '';
            const price = item.querySelector('.auctionValue')?.textContent?.trim() || '';
            const startPrice = item.querySelector('.auctionStartPrice')?.textContent?.trim() || '';
            const time = item.querySelector('.time-remaining')?.textContent?.trim() || '';
            return { name, rating, position, state, price, startPrice, time };
        })"""
    )
    
    return raw_listings
```

### Example 3: Determine Listing State
```python
def determine_state(state_text: str) -> ListingState:
    """Map WebApp state text to ListingState enum."""
    text = state_text.lower().strip()
    
    # Italian + English fallbacks
    if any(w in text for w in ["expired", "scadut", "expir"]):
        return ListingState.EXPIRED
    if any(w in text for w in ["active", "attiv", "selling", "vendita"]):
        return ListingState.ACTIVE
    if any(w in text for w in ["sold", "vendut", "completed"]):
        return ListingState.SOLD
    
    logger.warning(f"Stato listing non riconosciuto: '{state_text}'")
    return ListingState.UNKNOWN
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|-------------|-----------------|--------------|--------|
| Selenium + ChromeDriver | Playwright (sync/async) | ~2022-2023 | Faster, more reliable, no driver management |
| `time.sleep()` fixed delays | `wait_for_selector` / `wait_for_load_state` | Best practice | Eliminates race conditions |
| Single selector per element | Multiple fallback selectors | Community standard | Resilience to WebApp updates |
| Text-based element matching | CSS class-based matching | Community standard | Locale-independent |
| Manual DOM inspection | Browser DevTools + Network tab | Ongoing | Faster debugging |

**Deprecated/outdated:**
- Selenium-based tools (RelistingBot uses Selenium — outdated approach)
- Hardcoded sleep between actions
- Single-selector data extraction

---

## Open Questions

1. **Exact CSS selectors for FC 26 WebApp**
   - What we know: Community tools from FC 25/FC 26 era use `.listFUTItem`, `.ut-transfer-list-view`, `.auction-state`
   - What's unclear: Whether FC 26 has changed any class names since FC 25
   - Recommendation: Build with current selectors + add a "debug mode" that dumps page HTML when selectors fail. Test on live WebApp before committing to specific selectors.

2. **Internal WebApp API access**
   - What we know: Community tools access `getCurrentController()._listController._view._list.listRows` for structured data
   - What's unclear: Whether this is stable in FC 26, whether it triggers bot detection
   - Recommendation: Use DOM scraping as primary method (MEDIUM confidence), consider internal API as optimization only if DOM proves unreliable. Don't rely on internal API.

3. **Pagination on Transfer List**
   - What we know: Transfer List has a maximum of ~100 items; may paginate if more
   - What's unclear: Whether the current listing shows all items or requires scrolling/pagination
   - Recommendation: Check if `.listFUTItem` count matches expected items. If not, implement scroll-to-load or pagination detection.

4. **"Relist All" button availability**
   - What we know: Some WebApp versions have a "Relist All" button that relists all expired items at once
   - What's unclear: Whether FC 26 has this button, whether it's more reliable than individual relist
   - Recommendation: Check for "Relist All" button first (Phase 3). If present, prefer it over individual relisting (fewer actions = less bot detection risk).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (suggested, not yet installed) |
| Config file | none — see Wave 0 |
| Quick run command | `pytest tests/test_detector.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BROWSER-04 | Navigate to My Listings | integration | `pytest tests/test_navigator.py::test_go_to_transfer_list -x` | ❌ Wave 0 |
| DETECT-01 | Detect expired listings | unit | `pytest tests/test_detector.py::test_determine_state_expired -x` | ❌ Wave 0 |
| DETECT-02 | Read player name/rating/price | unit | `pytest tests/test_detector.py::test_parse_listing_data -x` | ❌ Wave 0 |
| DETECT-03 | Distinguish active vs expired | unit | `pytest tests/test_detector.py::test_determine_state -x` | ❌ Wave 0 |
| DETECT-04 | Detect empty listings | unit | `pytest tests/test_detector.py::test_empty_state -x` | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_detector.py` — unit tests for parsing and state detection
- [ ] `tests/test_navigator.py` — integration test for navigation (requires live WebApp or mock)
- [ ] `tests/test_listing_model.py` — unit tests for dataclass validation
- [ ] `pytest` install: `pip install pytest` — not in requirements.txt
- [ ] Mock HTML fixtures for unit testing without live WebApp

### Sampling Rate
- **Per task commit:** `pytest tests/test_detector.py tests/test_listing_model.py -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** All unit tests green + manual integration test on live WebApp

---

## Sources

### Primary (HIGH confidence)
- Playwright Python docs — `query_selector_all`, `eval_on_selector_all`, `wait_for_selector`, `wait_for_load_state`
- Existing codebase (`browser/controller.py`, `browser/auth.py`) — architecture patterns, selector dict pattern
- `config/config.json` — `rate_limiting`, `scan_interval_seconds` fields

### Secondary (MEDIUM confidence)
- fut23tamperScript.js (hearimm/GitHub) — CSS selectors: `.listFUTItem.player`, `.listFUTItem.auction`, `.ut-transfer-list-view`, `.sectioned-item-list`, controller names
- FSU EAFC FUT WEB Enhancer v26.05 (futcd_kcka/Greasy Fork) — FC 26 compatible, confirmed transfer list patterns, "Auto Relist" feature
- fut-trade-enhancer (ckalgos/GitHub) — transfer list automation patterns, autolist feature
- EasyFUT (Kava4/GitHub) — auto-relist feature for FC WebApp
- FUTFC.gg EA FC 26 Web App guide — navigation structure, Transfer Market access flow
- FIFAUTeam FC 26 Web App guide — WebApp features, transfer list management

### Tertiary (LOW confidence)
- RelistingBot (MrXELy/GitHub) — Selenium-based relist automation (outdated approach, but confirms relist concept)
- EA Help article on Transfer Market access — confirms unlock requirements, ban policies
- MagicBuyer-UT (AMINE1921/GitHub) — JS-based autobuyer, confirms internal API access pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Playwright already in project, no new deps needed
- Architecture: HIGH — Navigator/Detector separation is proven pattern
- CSS selectors: MEDIUM — Based on community tools, not official EA docs; FC 26 may have changed selectors
- Pitfalls: HIGH — Well-documented by community tools and scraping guides
- Data model: HIGH — Simple dataclass, straightforward design

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (30 days — WebApp may update with FC 26 seasonal changes)

**Note:** This research should be validated against a live FC 26 WebApp session before implementation. The CSS selectors are based on community tools and may need adjustment if FC 26 has updated its DOM structure.

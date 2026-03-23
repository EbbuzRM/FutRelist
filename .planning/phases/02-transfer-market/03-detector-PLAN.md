# Task 03: Listing Detector

**Wave:** 2
**Requirements:** DETECT-01, DETECT-02, DETECT-03, DETECT-04
**Depends on:** T01 (models/listing.py)
**Files created:** `browser/detector.py`
**Files modified:** none

---

## Objective

Create the `ListingDetector` class that reads listing state from the DOM after the navigator has reached the Transfer List view. Handles empty state detection, player data extraction, state mapping, and price/rating parsing.

---

## What to Build

### File: `browser/detector.py`

**Imports:**
```python
import re
import logging
from playwright.sync_api import Page
from models.listing import ListingState, PlayerListing, ListingScanResult
```

**SELECTORS dict:**
```python
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

**Standalone helper functions:**

`parse_price(text: str | None) -> int | None`
- If `text` is None or empty → return `None`
- Strip all non-digit chars via `re.sub(r'[^\d]', '', text)`
- Return `int(digits)` if digits found, else `None`
- Example: `"10,000 coins"` → `10000`

`parse_rating(text: str | None) -> int | None`
- If `text` is None or empty → return `None`
- Extract first digit sequence via `re.search(r'\d+', text)`
- Return `int(match.group())` if found, else `None`

`determine_state(state_text: str) -> ListingState`
- Lowercase and strip the input
- Check Italian + English keywords:
  - EXPIRED: "expired", "scadut", "expir"
  - ACTIVE: "active", "attiv", "selling", "vendita"
  - SOLD: "sold", "vendut", "completed"
- Default: `ListingState.UNKNOWN` + log warning
- This covers DETECT-01 (expired detection) and DETECT-03 (active vs expired distinction)

**ListingDetector class:**

Constructor: `__init__(self, page: Page)`
- Store `page`

Method: `scan_listings() -> ListingScanResult`
- Step 1: Check for empty state
  - Try `page.query_selector(SELECTORS["empty_state"])` → if found, return `ListingScanResult.empty()`
  - Try `page.query_selector_all(SELECTORS["listing_items"])` → if empty list, return `ListingScanResult.empty()`
  - This covers DETECT-04
- Step 2: Bulk extract using `page.eval_on_selector_all()`
  - JavaScript that maps each `.listFUTItem` to `{ name, rating, position, state, price, startPrice, time }`
  - Uses nested `querySelector` calls with the selectors from SELECTORS dict
- Step 3: Convert raw dicts to `PlayerListing` objects
  - For each raw dict (enumerate for index):
    - `parse_rating(raw["rating"])` → `rating`
    - `parse_price(raw["price"])` → `current_price`
    - `parse_price(raw["startPrice"])` → `start_price`
    - `determine_state(raw["state"])` → `state`
    - Build `PlayerListing(index=i, player_name=raw["name"], ...)`
  - This covers DETECT-02 (read name/rating/price)
- Step 4: Build `ListingScanResult`
  - Count states: `active_count = sum(1 for l in listings if l.state == ListingState.ACTIVE)`
  - Same for expired_count, sold_count
  - `total_items = len(listings)`, `is_empty = total_items == 0`
- Return the `ListingScanResult`

Method: `_extract_single_listing(self, element) -> dict | None` (private, fallback)
- If `eval_on_selector_all` fails or returns unexpected data, fall back to per-element extraction
- Uses `element.query_selector()` for each field
- Returns dict or None on failure

---

## Implementation Notes

- Use `eval_on_selector_all` for bulk extraction (more efficient than per-element queries)
- Handle `None` gracefully everywhere — sold items may have no price/time, unknown states may have no text
- Italian log messages matching existing codebase
- Follow auth.py error handling pattern (try/except, log, return safe default)

---

## Verification

```bash
# Automated: Run detector tests via pytest
pytest tests/test_detector.py -x --tb=short

# Import smoke test
python -c "from browser.detector import ListingDetector, SELECTORS, parse_price, parse_rating, determine_state; print('OK')"
```

Both `parse_price`, `parse_rating`, and `determine_state` unit tests are covered by `tests/test_detector.py` (created by Wave 0 task 00-test-setup). No inline `python -c` assertions needed for those functions — pytest handles it.

The import smoke test remains as a quick sanity check that the module loads without errors.

---

## Done Criteria

- [ ] `browser/detector.py` exists
- [ ] `SELECTORS` dict with all 14 keys from research
- [ ] `parse_price()` handles formatted strings, integers, None, empty
- [ ] `parse_rating()` handles "87", "OVR 91", None, empty
- [ ] `determine_state()` maps English + Italian state text to ListingState enum
- [ ] `ListingDetector.scan_listings()` returns `ListingScanResult`
- [ ] Empty state detection works (returns `ListingScanResult.empty()`)
- [ ] `_extract_single_listing()` fallback method tested (per-element extraction when bulk fails)
- [ ] All unit tests pass

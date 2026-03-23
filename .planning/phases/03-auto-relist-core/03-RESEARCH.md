# Phase 3: Auto-Relist Core - Research

**Researched:** 2026-03-23
**Domain:** Browser automation for FIFA WebApp transfer list relisting, Playwright sync API interaction patterns
**Confidence:** MEDIUM

## Summary

Phase 3 implements the core relisting automation — clicking "Relist" on expired players, applying price adjustments, and handling confirmation dialogs. The existing Phase 2 infrastructure (detector, navigator, models) provides the foundation: expired listings are already identified via `listing.needs_relist`, and the `relist_button` selector already exists in `detector.py` SELECTORS.

**Primary recommendation:** Build `browser/relist.py` as a `RelistExecutor` class following the navigator pattern (Page object + SELECTORS + _random_delay + Italian logging + bool returns), with standalone `calculate_adjusted_price()` function for testability. Integrate via Playwright's scoped element selection (`locator.filter()` + child locator) to click relist buttons within each expired listing element.

**Key architectural decision:** The FIFA WebApp relist flow has two modes — individual relist (click relist per listing, may show price edit + confirmation) and "Relist All" (single button relists everything at old prices). Phase 3 should support both, defaulting to individual relist for price adjustment support.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RELIST-01 | System relists expired players with one-click action | Playwright scoped click via `locator.filter()` + child selector. Existing `relist_button` selector in detector.py. Individual or bulk relist modes available. |
| RELIST-02 | System applies configurable price adjustment (fixed or percentage) | `listing_defaults.price_adjustment_type` and `price_adjustment_value` already in config.json. Standalone `calculate_adjusted_price()` handles both types. Price input uses `locator.fill()`. |
| RELIST-03 | System confirms relisting action completed successfully | Post-click state verification: re-scan listing state or check for success indicators. DOM state change detection after relist click. |
| RELIST-04 | System handles relist confirmation dialogs | Playwright `page.on("dialog", lambda dialog: dialog.accept())` pattern — documented in official Playwright docs. Must register handler BEFORE clicking. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| playwright | >= 1.40.0 | Browser automation (already in requirements.txt) | Already in project, sync API used throughout |
| Python dataclasses | 3.13 stdlib | Data model for RelistResult | Already used in models/listing.py |
| re | 3.13 stdlib | Price string parsing | Already used in detector.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| random | 3.13 stdlib | Rate limiting delays | Already used in navigator.py |
| logging | 3.13 stdlib | Italian log messages | Already used throughout |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Individual relist click per listing | "Relist All" bulk button | Relist All is simpler but can't apply per-listing price adjustments. Use individual for RELIST-02 compliance. |
| Page locator scoped clicks | `eval_on_selector_all` JS bulk operation | JS bulk is faster but fragile for click interactions with dialogs. Scoped clicks handle dialogs naturally. |

**Installation:** No new dependencies needed — uses existing playwright and stdlib.

## Architecture Patterns

### Recommended Project Structure
```
browser/
├── relist.py          # NEW — RelistExecutor class + calculate_adjusted_price()
├── navigator.py       # existing
├── detector.py        # existing
└── controller.py      # existing
models/
├── listing.py         # existing — add RelistResult dataclass? or keep in relist.py
tests/
├── test_relist.py     # NEW — unit tests for price adjustment + result model
```

### Pattern 1: RelistExecutor (Navigator Pattern)
**What:** Class wrapping Playwright Page + config for relisting actions, following the established TransferMarketNavigator pattern.
**When to use:** Any browser interaction module in this project.
**Example:**
```python
# Follows pattern from browser/navigator.py
import logging
import random
from typing import Optional
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

SELECTORS = {
    "relist_button": 'button:has-text("Relist"), .relist-btn',
    "relist_all_button": 'button:has-text("Relist All"), .relist-all-btn',
    "price_input": 'input[type="number"], .price-input, .ut-price-input input',
    "confirm_button": 'button:has-text("Confirm"), button:has-text("Ok"), .btn-action',
    "listing_items": '.listFUTItem.player',
    "success_indicator": '.notification-success, .toast-success',
}

class RelistExecutor:
    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        rate_limiting = config.get("rate_limiting", {})
        self.min_delay_ms = rate_limiting.get("min_delay_ms", 2000)
        self.max_delay_ms = rate_limiting.get("max_delay_ms", 5000)

    def _random_delay(self, min_ms=None, max_ms=None):
        # same as navigator pattern
        ...
```
**Source:** Follows `browser/navigator.py` TransferMarketNavigator pattern (verified in codebase)

### Pattern 2: Scoped Click for Relist Button
**What:** Click the relist button within a specific listing element using Playwright's locator chaining.
**When to use:** Clicking relist on individual expired listings.
**Example:**
```python
# Source: https://github.com/microsoft/playwright/blob/main/docs/src/locators.md
# Pattern: locator.filter(has=child).locator(button).click()
for listing in expired_listings:
    listing_el = self.page.locator(SELECTORS["listing_items"]).nth(listing.index)
    relist_btn = listing_el.locator(SELECTORS["relist_button"])
    relist_btn.click()
    self._random_delay()
```

### Pattern 3: Dialog Handler Registration
**What:** Register a dialog event handler BEFORE clicking relist to auto-accept confirmation popups.
**When to use:** Before any relist click that may trigger a confirmation dialog.
**Example:**
```python
# Source: https://github.com/microsoft/playwright/blob/main/docs/src/api/class-dialog.md
# Python sync API
def handle_dialog(self, dialog):
    logger.info(f"Dialog rilevato: {dialog.message}")
    dialog.accept()

# Register BEFORE clicking:
self.page.on("dialog", self.handle_dialog)
# Then click:
listing_el.locator(SELECTORS["relist_button"]).click()
```

### Pattern 4: Price Adjustment Calculation (Standalone Function)
**What:** Pure function for calculating adjusted prices — testable without browser.
**When to use:** Before filling price inputs during relist.
**Example:**
```python
def calculate_adjusted_price(
    current_price: int,
    adjustment_type: str,
    adjustment_value: float,
    min_price: int = 200,
    max_price: int = 15_000_000,
) -> int:
    """Calcola il prezzo aggiustato per il rilist."""
    if adjustment_type == "percentage":
        adjusted = current_price * (1 + adjustment_value / 100)
    elif adjustment_type == "fixed":
        adjusted = current_price + adjustment_value
    else:
        logger.warning(f"Tipo aggiustamento sconosciuto: {adjustment_type}")
        return current_price
    # Clamp to FIFA price bounds
    return max(min_price, min(max_price, int(adjusted)))
```

### Anti-Patterns to Avoid
- **Clicking relist without dialog handler registered:** Playwright will hang if a dialog appears and no handler is registered. Always register before clicking.
- **No delay between relist actions:** Triggers EA soft ban (rate limit). Use `_random_delay()` between every action.
- **Modifying listing model in place:** Keep `RelistResult` as a separate dataclass to track action outcomes without mutating the scan data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dialog handling | Custom JS injection to suppress popups | Playwright `page.on("dialog", ...)` | Official Playwright API handles all dialog types (confirm, alert, prompt) natively |
| Price input clearing | Manual triple-click + delete | `locator.fill("")` or `locator.clear()` | Playwright handles focus, clear, and input events correctly |
| Scoped element selection | Complex CSS nth-child selectors | `page.locator().nth(index)` or `locator.filter(has=...)` | Playwright locators are the standard, handle waits automatically |
| Rate limiting delay | Fixed `time.sleep()` | `page.wait_for_timeout(random.randint(min, max))` | Non-blocking, matches existing navigator pattern, randomized for anti-detection |

**Key insight:** Playwright's built-in actionability checks and dialog handling are designed exactly for this use case — don't reinvent them with raw JS injection or sleep calls.

## Common Pitfalls

### Pitfall 1: EA Soft Ban from Too-Fast Relisting
**What goes wrong:** Clicking relist on multiple listings too quickly triggers EA's rate limiter. Transfer market shows "Sorry, an error has occurred" for all subsequent actions.
**Why it happens:** EA detects non-human timing patterns. Too many actions per minute = bot detection.
**How to avoid:** Use `_random_delay()` between every relist click (2000-5000ms from config). Consider longer pauses every N actions.
**Warning signs:** "error occurred" message, "transfer market heating up" message, actions silently failing.

### Pitfall 2: Dialog Appears After Price Edit, Not After Relist Click
**What goes wrong:** Assuming the confirmation dialog appears immediately on relist click. In FIFA WebApp, the flow is: click relist → optionally edit price → click confirm → dialog may appear.
**Why it happens:** The WebApp relist flow can be 2-3 steps, not just one click.
**How to handle:** After clicking relist, wait for price input to appear. If it appears, fill it and click confirm. Register dialog handler before the entire sequence.
**Warning signs:** Script hangs after relist click, "waiting for element" timeout.

### Pitfall 3: Relist All vs Individual Relist Confusion
**What goes wrong:** Using "Relist All" button when price adjustment is configured. Relist All re-lists at previous prices without modification.
**Why it happens:** "Relist All" is a single-button convenience that bypasses per-listing price entry.
**How to avoid:** Use individual relist flow when `price_adjustment_value != 0`. Use "Relist All" only when no price adjustment needed (value = 0).
**Warning signs:** Prices not changing after relist, requirement RELIST-02 not satisfied.

### Pitfall 4: Selector Fragility Across FIFA Versions
**What goes wrong:** CSS selectors break when EA updates the WebApp (happens mid-season).
**Why it happens:** EA uses dynamic class names, and the WebApp is a React SPA with changing DOM structure.
**How to avoid:** Use multiple fallback selectors in SELECTORS dict (already done: `button:has-text("Relist"), .relist-btn`). Keep selectors in the module-level SELECTORS dict for easy updates.
**Warning signs:** "element not found" errors, empty results from scan.

## Code Examples

Verified patterns from official sources:

### Scoped Click Within Listing Element
```python
# Source: Playwright docs - locators.md filter+locator pattern
# Python sync API
listing_el = page.locator(".listFUTItem.player").nth(0)
relist_btn = listing_el.locator('button:has-text("Relist")')
relist_btn.click()
```

### Dialog Handler Registration (Sync API)
```python
# Source: https://github.com/microsoft/playwright/blob/main/docs/src/api/class-dialog.md
from playwright.sync_api import sync_playwright

def handle_dialog(dialog):
    print(dialog.message)
    dialog.accept()

page.on("dialog", handle_dialog)
# Now any dialog that appears will be auto-accepted
```

### Fill Price Input
```python
# Source: Playwright docs - input.md fill()
price_input = page.locator('input[type="number"]')
price_input.clear()
price_input.fill("45000")
```

### Sequential Actions with Delay
```python
# Source: existing browser/navigator.py pattern
for listing in expired_listings:
    # Click relist
    element.locator(SELECTORS["relist_button"]).click()
    page.wait_for_timeout(2000)  # Wait for UI response

    # Check if price input appeared
    price_input = page.query_selector(SELECTORS["price_input"])
    if price_input:
        new_price = calculate_adjusted_price(listing.current_price, ...)
        price_input.fill(str(new_price))
        page.locator(SELECTORS["confirm_button"]).click()

    # Rate limit delay
    self._random_delay()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium WebDriver clicks | Playwright sync API locators | Project uses Playwright since Phase 1 | Better waits, built-in actionability |
| Fixed sleep delays | Random delays from config | navigator.py pattern | Anti-detection, matches human behavior |
| JS injection for dialog handling | Playwright native dialog events | Playwright API feature | More reliable, handles all dialog types |

**Deprecated/outdated:**
- Selenium-based approaches (project chose Playwright)
- `time.sleep()` for delays (use `page.wait_for_timeout()`)
- Raw `page.click(selector)` (use `locator.click()` with auto-wait)

## Open Questions

1. **Does the FIFA WebApp relist flow show a price input by default?**
   - What we know: Community tools (fut-trade-enhancer, RelistingBot) show per-listing price edit capability
   - What's unclear: Whether clicking "Relist" immediately re-lists at old price, or opens a price editor first
   - Recommendation: Design for both — check if price input appears after relist click, fill if present, otherwise accept default

2. **Is there a "Relist All" button on the current WebApp?**
   - What we know: EA Forums mention "re-list all" functionality (2025-09 forum post about errors)
   - What's unclear: Exact CSS selector for the button
   - Recommendation: Include `relist_all_button` in SELECTORS with fallback selectors; test in Phase 3 integration

3. **What are the FIFA price bounds?**
   - What we know: Minimum listing price is 200 coins; maximum varies by card (typically 15M cap)
   - What's unclear: Whether there are different bounds for start price vs buy-now price
   - Recommendation: Use 200 as absolute minimum, config can specify max; handle price validation errors gracefully

4. **Does clicking relist on an expired listing immediately change its state in the DOM?**
   - What we know: The listing should transition from EXPIRED → ACTIVE after successful relist
   - What's unclear: Timing of the DOM update (instant vs after network request)
   - Recommendation: Wait for state change or success notification; add brief post-click verification

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.0.0 |
| Config file | none (uses defaults) |
| Quick run command | `pytest tests/test_relist.py -x --tb=short` |
| Full suite command | `pytest tests/ -x --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RELIST-01 | Click relist on expired listing | integration (needs browser) | manual test with live WebApp | ❌ Wave 0 |
| RELIST-02 | Price adjustment calculation (percentage) | unit | `pytest tests/test_relist.py::test_price_adjustment_percentage -x` | ❌ Wave 0 |
| RELIST-02 | Price adjustment calculation (fixed) | unit | `pytest tests/test_relist.py::test_price_adjustment_fixed -x` | ❌ Wave 0 |
| RELIST-02 | Price adjustment bounds clamping | unit | `pytest tests/test_relist.py::test_price_adjustment_bounds -x` | ❌ Wave 0 |
| RELIST-03 | RelistResult tracks success/failure | unit | `pytest tests/test_relist.py::test_relist_result -x` | ❌ Wave 0 |
| RELIST-04 | Dialog handler registration | integration (needs browser) | manual test | ❌ N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/test_relist.py -x --tb=short`
- **Per wave merge:** `pytest tests/ -x --tb=short`
- **Phase gate:** All unit tests green + manual browser test for click/dialog

### Wave 0 Gaps
- [ ] `tests/test_relist.py` — unit tests for `calculate_adjusted_price()` and `RelistResult`
- [ ] `browser/relist.py` — `RelistExecutor` class and `calculate_adjusted_price()` function
- [ ] No new framework install needed (pytest already in requirements.txt)

## Sources

### Primary (HIGH confidence)
- Playwright Dialog API docs — `page.on("dialog", ...)` pattern for Python sync API
- Playwright Locator docs — `locator.filter(has=...)` and scoped click patterns
- Playwright Input docs — `locator.fill()`, `locator.clear()` for price input handling
- Existing codebase — `browser/navigator.py` pattern (SELECTORS + _random_delay + bool returns), `browser/detector.py` SELECTORS (relist_button already defined)

### Secondary (MEDIUM confidence)
- fut-trade-enhancer gist — confirms `.listFUTItem.player` selector structure, auction state elements
- EA Forums (2025-09) — confirms "re-list all" functionality exists, mentions errors during relist
- FIFA WebApp community guides (2026) — confirms rate limiting / soft ban behavior

### Tertiary (LOW confidence)
- RelistingBot README — confirms relist automation is feasible with Selenium (old approach)
- Chrome Web Store FUT Lister — confirms relist automation tools exist for current FC version

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, uses existing Playwright + stdlib
- Architecture: HIGH — follows established navigator pattern from codebase
- Selectors: MEDIUM — `relist_button` already in detector.py SELECTORS but untested against live WebApp
- Dialog handling: HIGH — official Playwright API, well-documented
- Price adjustment: HIGH — pure math, easily testable
- Pitfalls: MEDIUM — soft ban thresholds based on community reports, not official EA docs

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (30 days — Playwright API is stable, FIFA WebApp selectors may change mid-season)

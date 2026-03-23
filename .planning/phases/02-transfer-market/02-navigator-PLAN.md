# Task 02: Transfer Market Navigator

**Wave:** 1
**Requirements:** BROWSER-04
**Depends on:** nothing (uses existing `browser/controller.py` and `config/config.json`)
**Files created:** `browser/navigator.py`
**Files modified:** none

---

## Objective

Create the `TransferMarketNavigator` class that navigates the EA FC WebApp from the home page to the Transfer List (My Listings) view. Follows the same patterns as `browser/auth.py` — centralized SELECTORS dict, Playwright sync API, logging.

---

## What to Build

### File: `browser/navigator.py`

**SELECTORS dict** (at top of module):
```python
SELECTORS = {
    "transfers_nav": 'button:has-text("Transfers"), .icon-transfer',
    "transfer_list_tab": 'button:has-text("Transfer List"), .ut-tile-transfer-list',
    "my_listings_view": '.ut-transfer-list-view, .sectioned-item-list',
    "loading_indicator": '.ut-loading-spinner, .loading',
}
```

Note: `auth.py` already defines `transfer_market` and `my_listings` selectors. Navigator should use its own more specific selectors for the navigation path: Home → Transfers sidebar → Transfer List tab. If selectors overlap, that's fine — redundancy for resilience.

**TransferMarketNavigator class:**

Constructor: `__init__(self, page: Page, config: dict)`
- Store `page` and `config`
- Extract delay settings from `config["rate_limiting"]` (min_delay_ms, max_delay_ms)

Method: `go_to_transfer_list() -> bool`
- Step 1: Click Transfers button in sidebar (`SELECTORS["transfers_nav"]`)
  - Use `page.query_selector()`, check for None, log error if not found
  - Click, then wait 2-3s (use `page.wait_for_timeout()` with configured delay)
  - `self._random_delay()`
- Step 2: Click Transfer List tab (`SELECTORS["transfer_list_tab"]`)
  - Same pattern: query → check → click → wait
  - `self._random_delay()`
- Step 3: Wait for listing view to be ready
  - `page.wait_for_load_state("networkidle", timeout=15000)`
  - `page.wait_for_selector(SELECTORS["my_listings_view"], state="visible", timeout=10000)`
- Return `True` on success, `False` on any failure
- Wrap entire method in try/except, log errors, return `False`

**Helper:** `_random_delay(self, min_ms: int = None, max_ms: int = None) -> None`
- Generate random delay between min and max (from config defaults if not specified)
- Use `page.wait_for_timeout(delay)`
- Adds bot-detection resistance

---

## Implementation Notes

- Follow `auth.py` patterns exactly: same logging style, same error handling, same selector dict pattern
- Do NOT use `time.sleep()` — always use `page.wait_for_timeout()` or Playwright waits
- Italian log messages to match existing codebase
- The method returns `bool` (not raising exceptions) to match auth.py's `perform_login()` pattern

---

## Verification

```bash
# Import test
python -c "from browser.navigator import TransferMarketNavigator, SELECTORS; print('OK')"

# Selector completeness check
python -c "
from browser.navigator import SELECTORS
required = ['transfers_nav', 'transfer_list_tab', 'my_listings_view', 'loading_indicator']
for key in required:
    assert key in SELECTORS, f'Missing selector: {key}'
print('All selectors present')
"
```

---

## Done Criteria

- [ ] `browser/navigator.py` exists
- [ ] `SELECTORS` dict at top of module with 4 keys
- [ ] `TransferMarketNavigator` class with `__init__(page, config)` and `go_to_transfer_list() -> bool`
- [ ] `_random_delay` helper uses config rate_limiting values
- [ ] No `time.sleep()` usage
- [ ] Italian log messages
- [ ] Import test passes

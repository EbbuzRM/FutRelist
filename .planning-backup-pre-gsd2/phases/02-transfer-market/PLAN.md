# Phase 2: Transfer Market Navigation

## Phase Overview

**Goal:** Enable the tool to navigate to the Transfer List, detect player listing states (active/expired/sold), and extract listing data (name, rating, price). This is the detection half of the relist loop — Phase 3 will act on the detected data.

**Requirements addressed:**
- BROWSER-04: System navigates to Transfer Market > My Listings automatically
- DETECT-01: System detects when player listings have expired
- DETECT-02: System reads player name, rating, and current listing price
- DETECT-03: System distinguishes between active and expired listings
- DETECT-04: System detects "no listings" state (empty transfer list)

---

## Architecture

```
BrowserController (Phase 1, exists)
    └── AuthManager (Phase 1, exists)
        └── TransferMarketNavigator (NEW — navigator.py)
            └── ListingDetector (NEW — detector.py)
                └── PlayerListing / ListingScanResult (NEW — listing.py)
```

**Key patterns from research:**
- CSS selector centralization (dict at top of module, like auth.py)
- Wait-for-ready before extraction (networkidle + visible selector)
- Navigator/Detector separation (navigation vs data extraction)
- Italian locale fallbacks for state text detection

---

## Task Breakdown & Wave Structure

| Wave | Task | File(s) | Requirements | Depends On |
|------|------|---------|-------------|------------|
| 1 | T01: Listing Data Model | `models/__init__.py`, `models/listing.py` | DETECT-01, DETECT-02, DETECT-03, DETECT-04 | — |
| 1 | T02: Transfer Market Navigator | `browser/navigator.py` | BROWSER-04 | — (uses existing controller.py) |
| 2 | T03: Listing Detector | `browser/detector.py` | DETECT-01, DETECT-02, DETECT-03, DETECT-04 | T01 (model types) |
| 3 | T04: Integration | `main.py` | BROWSER-04, DETECT-01-04 | T01, T02, T03 |

**Wave 1 parallelism:** T01 (model) and T02 (navigator) touch completely different files and have no code dependencies. They can execute simultaneously.

**Wave 2:** T03 (detector) imports types from `models/listing.py` — must wait for T01.

**Wave 3:** T04 (integration) wires everything into `main.py` — must wait for all.

---

## Must-Haves (Goal-Backward Verification)

### Observable Truths
1. User runs the tool → browser opens, logs in, navigates to Transfer List automatically
2. System shows listing count and player details in console output
3. System correctly identifies which listings are expired vs active vs sold
4. System handles empty Transfer List without crashing
5. System handles missing/changed CSS selectors gracefully (logs warning, doesn't crash)

### Required Artifacts
| File | Provides | Exports/Contains |
|------|----------|-----------------|
| `models/__init__.py` | Package marker | — |
| `models/listing.py` | Data structures | `PlayerListing`, `ListingState`, `ListingScanResult` |
| `browser/navigator.py` | Page navigation | `TransferMarketNavigator`, `go_to_transfer_list()` |
| `browser/detector.py` | DOM data extraction | `ListingDetector`, `scan_listings()`, `determine_state()`, `parse_price()` |
| `main.py` (modified) | Integration | Navigator + Detector wired into main loop |

### Key Links
| From | To | Via | Failure Mode |
|------|----|-----|-------------|
| `main.py` | `navigator.go_to_transfer_list()` | import + call after login | Login works but tool stops at home |
| `navigator.py` | Playwright Page | `page.click()` + `wait_for_selector` | Race condition, empty page |
| `detector.py` | `.listFUTItem` DOM | `query_selector_all` | Selector breakage after WebApp update |
| `detector.py` | `models.listing` | import ListingState, PlayerListing | Type errors, wrong state mapping |

---

## Plan Execution Order

| Plan | File | Description |
|------|------|-------------|
| 01 | `01-listing-model-PLAN.md` | Data model (ListingState enum, PlayerListing dataclass, ListingScanResult) |
| 02 | `02-navigator-PLAN.md` | Transfer Market navigation (TransferMarketNavigator class) |
| 03 | `03-detector-PLAN.md` | Listing state detection (ListingDetector class + parsing helpers) |
| 04 | `04-integration-PLAN.md` | Wire into main.py |

---

## Verification

### Per-Task
- T01: Python imports succeed, dataclass instantiation works, `needs_relist` property correct
- T02: `navigator.py` imports without error, SELECTORS dict has all required keys, `go_to_transfer_list()` has correct method signature
- T03: `detector.py` imports without error, `determine_state()` maps correctly for all states, `parse_price()` handles edge cases, `scan_listings()` returns `ListingScanResult`
- T04: `main.py` runs without import errors, prints listing summary after login

### Phase Gate
- All unit tests pass: `pytest tests/test_detector.py tests/test_listing_model.py -x`
- Manual integration: run `python main.py`, verify it navigates to Transfer List and prints listing summary

---

## Research Reference

Full research: `.planning/research/phase2-RESEARCH.md`
- CSS selectors for EA FC WebApp (MEDIUM confidence — community-reverse-engineered)
- Navigator/Detector architecture pattern
- Wait-for-ready pattern
- Anti-patterns: no `time.sleep`, no single-selector extraction, no locale-dependent text matching

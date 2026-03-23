# Task 00: Test Infrastructure Setup

**Wave:** 0
**Requirements:** DETECT-01, DETECT-02, DETECT-03, DETECT-04
**Depends on:** nothing
**Files created:** `tests/__init__.py`, `tests/conftest.py`, `tests/test_listing_model.py`, `tests/test_detector.py`
**Files modified:** `requirements.txt` (add pytest)

---

## Objective

Set up pytest test infrastructure before implementation begins. Creates test files, mock fixtures, and installs pytest. This Wave 0 task enables automated verification for all subsequent Phase 2 tasks (T01-T04), replacing inline `python -c` verification with proper pytest commands.

---

## What to Build

### File 1: `requirements.txt` (modified)
Add `pytest>=7.0.0` to requirements.txt (append on new line).

### File 2: `tests/__init__.py`
Empty package marker file.

### File 3: `tests/conftest.py`
Shared pytest fixtures:

- `sample_listing_html` fixture: Returns a string with mock HTML matching the WebApp DOM structure. Must contain:
  - A `.listFUTItem.player` element with nested: `.player-name` ("Mbappé"), `.rating` ("91"), `.position` ("ST"), `.auction-state` ("Expired"), `.auctionValue` ("50,000 coins"), `.auctionStartPrice` ("45,000"), `.time-remaining` ("")
  - A second `.listFUTItem.player` element with: `.player-name` ("Messi"), `.rating` ("90"), `.position` ("RW"), `.auction-state` ("Active"), `.auctionValue` ("30,000 coins"), `.auctionStartPrice` ("28,000"), `.time-remaining` ("2h 30m")
  - A third `.listFUTItem.player` element with: `.player-name` ("Haaland"), `.rating` ("89"), `.position` ("ST"), `.auction-state` ("Sold"), `.auctionValue` ("40,000 coins"), `.auctionStartPrice` ("38,000"), `.time-remaining` ("")

- `empty_listings_html` fixture: Returns HTML with just `.no-items` element (no listing items).

### File 4: `tests/test_listing_model.py`
Unit tests for the data model (to be implemented in `models/listing.py`):

- `test_listing_state_values`: Assert ListingState has ACTIVE, EXPIRED, SOLD, UNKNOWN with correct string values
- `test_player_listing_creation`: Create a PlayerListing with all fields, assert fields accessible
- `test_player_listing_needs_relist`: Assert needs_relist is True for EXPIRED, False for ACTIVE/SOLD/UNKNOWN
- `test_listing_scan_result_empty`: Call ListingScanResult.empty(), assert is_empty=True, all counts 0, listings=[]
- `test_listing_scan_result_counts`: Create ListingScanResult with listings, verify counts

NOTE: These tests will fail until T01 creates the models. That's expected — Wave 0 files exist before implementation.

### File 5: `tests/test_detector.py`
Unit tests for detector functions (to be implemented in `browser/detector.py`):

- `test_parse_price_formatted`: parse_price("10,000 coins") == 10000
- `test_parse_price_plain`: parse_price("500") == 500
- `test_parse_price_none`: parse_price(None) is None
- `test_parse_price_empty`: parse_price("") is None
- `test_parse_price_no_digits`: parse_price("no numbers") is None
- `test_parse_rating_normal`: parse_rating("87") == 87
- `test_parse_rating_with_prefix`: parse_rating("OVR 91") == 91
- `test_parse_rating_none`: parse_rating(None) is None
- `test_parse_rating_empty`: parse_rating("") is None
- `test_determine_state_expired_english`: determine_state("Expired") == ListingState.EXPIRED
- `test_determine_state_expired_italian`: determine_state("scaduto") == ListingState.EXPIRED
- `test_determine_state_active_english`: determine_state("Active") == ListingState.ACTIVE
- `test_determine_state_active_italian`: determine_state("attivo") == ListingState.ACTIVE
- `test_determine_state_sold_english`: determine_state("Sold") == ListingState.SOLD
- `test_determine_state_sold_italian`: determine_state("venduto") == ListingState.SOLD
- `test_determine_state_unknown`: determine_state("???") == ListingState.UNKNOWN

NOTE: These tests import from browser.detector which won't exist until T03. This is expected for Wave 0.

---

## Implementation Notes

- Tests import from modules that don't exist yet (models/listing.py, browser/detector.py). This is normal for Wave 0 — tests define the contract before implementation.
- conftest.py uses raw HTML strings, not Playwright Page objects — no browser needed for unit tests.
- Follow pytest conventions: test files prefixed with `test_`, test functions prefixed with `test_`.
- Italian text in test data (e.g., "scaduto", "attivo") matches WebApp locale.

---

## Verification

```bash
# Install pytest
pip install pytest

# Run model tests (will fail until T01 — that's expected)
pytest tests/test_listing_model.py -x --tb=short

# Run detector tests (will fail until T03 — that's expected)
pytest tests/test_detector.py -x --tb=short

# Run full test suite
pytest tests/ -v --tb=short
```

---

## Done Criteria

- [ ] `pip install pytest` succeeds
- [ ] `tests/__init__.py` exists
- [ ] `tests/conftest.py` exists with sample_listing_html and empty_listings_html fixtures
- [ ] `tests/test_listing_model.py` exists with 5 test functions
- [ ] `tests/test_detector.py` exists with 16 test functions
- [ ] `pytest tests/ --collect-only` succeeds (all test files are parseable)
- [ ] `requirements.txt` includes pytest>=7.0.0

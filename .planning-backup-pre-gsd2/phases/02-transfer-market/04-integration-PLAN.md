# Task 04: Integration into main.py

**Wave:** 3
**Requirements:** BROWSER-04, DETECT-01, DETECT-02, DETECT-03, DETECT-04
**Depends on:** T01 (models), T02 (navigator), T03 (detector)
**Files created:** none
**Files modified:** `main.py`

---

## Objective

Wire the navigator and detector into `main.py` so that after successful login, the tool navigates to the Transfer List, scans listings, and prints a summary. This replaces the current placeholder message "Browser pronto per operazioni (rilisting, ecc.)" with actual functionality.

---

## What to Build

### Changes to `main.py`

**New imports** (after existing imports, line ~14):
```python
from browser.navigator import TransferMarketNavigator
from browser.detector import ListingDetector
```

**Replace lines 102-103** (the "=== Autenticazione completata ===" + "Browser pronto per operazioni" messages) with:

```
logger.info("=== Autenticazione completata ===")

# Phase 2: Navigate to Transfer List and scan listings
navigator = TransferMarketNavigator(page, config)
detector = ListingDetector(page)

logger.info("Navigazione verso Transfer List...")
if navigator.go_to_transfer_list():
    logger.info("Transfer List raggiunta, scansione listing...")
    result = detector.scan_listings()

    if result.is_empty:
        logger.info("Nessun listing trovato sul Transfer List")
    else:
        logger.info(f"=== Scan completata: {result.total_items} listing trovati ===")
        logger.info(f"  Attivi: {result.active_count}")
        logger.info(f"  Scaduti: {result.expired_count}")
        logger.info(f"  Venduti: {result.sold_count}")

        if result.expired_count > 0:
            logger.info(f"-> {result.expired_count} listing scaduti da rilistare (Phase 3)")
            for listing in result.listings:
                if listing.needs_relist:
                    logger.info(f"  [{listing.index}] {listing.player_name} OVR {listing.rating} - {listing.current_price or '?'} coins")
else:
    logger.error("Impossibile raggiungere il Transfer List")
```

**Keep** the existing `input("\nPremi INVIO per chiudere il browser...")` and cleanup code below unchanged.

---

## Implementation Notes

- Do NOT remove the existing browser cleanup logic (try/except/finally blocks)
- Do NOT modify `setup_logging()`, `load_config()`, `get_credentials()`, or the login flow
- Only modify the section between login completion and the `input()` prompt
- Keep the tool interactive — user still presses ENTER to close
- Log output should be clear and structured (the summary block above)

---

## Verification

```bash
# Import test — should not fail on new imports
python -c "import main; print('OK')"

# Static check — verify navigator and detector are imported
python -c "
import ast, sys
with open('main.py') as f:
    tree = ast.parse(f.read())
imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
assert 'TransferMarketNavigator' in str(imports), 'Missing TransferMarketNavigator import'
assert 'ListingDetector' in str(imports), 'Missing ListingDetector import'
print('Imports verified')
"
```

### Manual Integration Test
1. Run `python main.py`
2. Verify: browser opens, logs in, navigates to Transfer List
3. Verify: console shows listing summary with counts
4. Verify: if listings exist, player names/ratings are printed
5. Verify: if no listings, shows "Nessun listing trovato" message
6. Press ENTER → browser closes cleanly

---

## Done Criteria

- [ ] `main.py` imports `TransferMarketNavigator` and `ListingDetector`
- [ ] After login, tool navigates to Transfer List automatically
- [ ] Console output shows listing summary (total, active, expired, sold counts)
- [ ] Expired listings are individually listed with player name, rating, price
- [ ] Empty Transfer List shows "Nessun listing trovato" without crashing
- [ ] Navigation failure shows error but doesn't crash the tool
- [ ] Existing cleanup code (browser stop) still works

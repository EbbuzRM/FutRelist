# Task: Golden Hour Wait Fix (Cycle 1 & Precision)

**Wave:** 1
**Requirements:** GOLDEN-FIX-04
**Depends on:** Startup Blindness Fix (Cycle 1 logic)
**Files modified:** `main.py`, `tests/test_golden_timeline.py`

---

## Objective

Prevent the bot from getting stuck in a long `time.sleep()` when started during a Golden Hour HOLD period (e.g., at 17:21). The bot must perform a full scan first, then enter a normal HOLD state (Home page) with heartbeats and Telegram responsiveness.

---

## Implementation Details

### File: `main.py`

**Modify the `--- WAIT FOR EXACT GOLDEN TIME ---` block:**
```python
# --- WAIT FOR EXACT GOLDEN TIME ---
now = datetime.now()
next_golden = get_next_golden_hour(now)
if next_golden and is_in_golden_period(now) and now < next_golden:
    # Solo se siamo a ridosso della golden (:08-:12) facciamo l'attesa di precisione
    if is_close_to_golden(now) and not is_in_golden_window(now):
        wait_secs = (next_golden - now).total_seconds()
        logger.info(f"[Golden] Attesa precisa: {format_duration(int(wait_secs))} per le {next_golden.strftime('%H:%M:%S')}.")
        # Sostituisci time.sleep(wait_secs) con wait_interruptible() per non bloccare Telegram
        if bot_state.wait_interruptible(wait_secs):
            logger.info("[Reboot] Attesa precisione interrotta per reboot.")
            return # Reboot
        if bot_state.has_commands():
            logger.info("[Golden] Attesa precisione interrotta per processare comandi Telegram.")
            # Non facciamo return, lasciamo che il loop principale processi i comandi
    elif is_in_golden_window(now):
        logger.info(f"[Golden] Già nella finestra golden ({now.strftime('%H:%M:%S')}), procedo con scansione immediata.")
```

**Key Improvements:**
1. Added `is_close_to_golden(now)` guard: at 17:21, this block will be skipped, allowing the bot to proceed to `detector.scan_listings()`.
2. Used `bot_state.wait_interruptible(wait_secs)` instead of `time.sleep(wait_secs)`.
3. Handles Telegram commands immediately by breaking out of the sleep.

### File: `tests/test_golden_timeline.py`

**Update `_classify_behavior` to reflect the new logic:**
- Ensure the simulation correctly identifies that at 17:21, the bot should NOT be in "precision wait" but should proceed to scan (which is then followed by a normal HOLD).

---

## Verification Plan

### Automated Tests
```bash
# Esegui i test della timeline per verificare che non ci siano regressioni
python -m pytest c:\App\fifa-relist\tests\test_golden_timeline.py
```

### Manual Verification
1. Start the bot at 17:21 (or any time in HOLD period but outside :08-:12).
2. Verify it navigates to Transfer List and scans items.
3. Verify it logs "Attesa precisa" ONLY if started between :08 and :09:29.
4. Verify Telegram commands work during the HOLD period.

---

## Done Criteria

- [ ] `main.py` uses `is_close_to_golden` guard for precision wait.
- [ ] `time.sleep()` is replaced by `wait_interruptible()` in precision wait.
- [ ] Bot at 17:21 performs a full scan before entering HOLD.
- [ ] All 526+ tests in `test_golden_timeline.py` pass.

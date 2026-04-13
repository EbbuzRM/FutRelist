---
phase: golden-processing-retry
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - main.py
  - tests/test_golden_retry.py
autonomous: true
requirements: [GPR-01, GPR-02, GPR-03, GPR-04]
must_haves:
  truths:
    - "After relist during golden window, bot retries until all items are relisted or golden window closes"
    - "Each retry waits 5-10s (random), interruptible by Telegram/reboot"
    - "Each retry does a FRESH scan (not stale data)"
    - "Retry loop only activates during golden window — outside it, normal flow continues unchanged"
  artifacts:
    - path: "main.py"
      provides: "_golden_retry_relist helper function"
      contains: "_golden_retry_relist"
    - path: "tests/test_golden_retry.py"
      provides: "Unit tests for golden retry logic"
      min_lines: 50
  key_links:
    - from: "main.py (relist block ~line 902)"
      to: "_golden_retry_relist"
      via: "function call after initial relist when in golden window"
      pattern: "_golden_retry_relist"
    - from: "_golden_retry_relist"
      to: "is_in_golden_window"
      via: "loop condition check"
      pattern: "is_in_golden_window"
    - from: "_golden_retry_relist"
      to: "bot_state.wait_interruptible"
      via: "interruptible wait between retries"
      pattern: "wait_interruptible"
---

<objective>
Add a retry loop for Processing items during golden hours.

Purpose: After an initial relist during the golden window (:09-:11), EA may still have items in "Processing..." state that haven't transitioned to "Expired" yet. The bot needs to wait 5-10s, rescan, and relist any remaining expired/processing items — repeating until all items are relisted or the golden window closes.

Output: `_golden_retry_relist()` helper function in main.py, integrated into the main loop relist block, with unit tests.
</objective>

<execution_context>
@$HOME/.config/opencode/get-shit-done/workflows/execute-plan.md
@$HOME/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@main.py
@AGENTS.md
@browser/detector.py
@models/listing.py
@bot_state.py
@tests/test_golden_timeline.py

<interfaces>
<!-- Key types and functions the executor needs -->

From models/listing.py:
```python
class ListingState(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SOLD = "sold"
    PROCESSING = "processing"
    UNKNOWN = "unknown"

@dataclass
class ListingScanResult:
    total_count: int
    active_count: int
    expired_count: int        # includes PROCESSING items
    sold_count: int
    listings: list[PlayerListing]
    @property
    def processing_count(self) -> int: ...
```

From main.py (golden hour functions — DO NOT MODIFY):
```python
def is_in_golden_window(now: datetime) -> bool:
    """True if we're in the :09-:11 golden relist window."""
    # Returns: now.hour in GOLDEN_HOURS and now.minute in GOLDEN_RELIST_WINDOW

def is_in_hold_window(now: datetime) -> bool:
    """True if in golden period but NOT in golden window."""

def get_next_golden_hour(now: datetime) -> datetime | None: ...
```

From bot_state.py:
```python
class BotState:
    def wait_interruptible(self, seconds: float) -> bool:
        """Wait up to `seconds`, interrupted by reboot/commands. Returns True if reboot requested."""
    def has_commands(self) -> bool: ...
    def consume_force_relist(self) -> bool: ...
    def update_stats(self, cycle: int = 0, relisted: int = 0, failed: int = 0) -> None: ...
```

From browser/relist.py:
```python
class RelistExecutor:
    relist_mode: str  # "all" or "per_listing"
    def relist_all(self, count: int = 1) -> RelistBatchResult: ...
    def relist_single(self, listing) -> RelistResult: ...
    def check_session_valid(self) -> bool: ...
```

From main.py (existing helpers):
```python
def navigate_with_retry(navigator, page) -> bool: ...
def _handle_session_recovery(executor, auth, config, page, fifa_logger) -> bool: ...
def _save_error_screenshot(page, logger) -> None: ...
def _compute_next_wait(scan, now, fifa_logger) -> int: ...
def relist_expired_listings(executor, expired_listings) -> tuple[int, int]: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create _golden_retry_relist helper + unit tests</name>
  <files>main.py, tests/test_golden_retry.py</files>
  <behavior>
    - Test 1: Helper returns (0, 0) when NOT in golden window (no retry attempted)
    - Test 2: Helper retries and accumulates stats when scan finds expired items
    - Test 3: Helper exits loop when fresh scan shows expired_count == 0 (all relisted)
    - Test 4: Helper exits loop when golden window closes (is_in_golden_window returns False)
    - Test 5: Helper exits loop when wait_interruptible signals reboot (returns True)
    - Test 6: Helper waits 5-10s between retries (random, verified via mock)
    - Test 7: Helper navigates and does fresh scan each retry (verified navigator/detector called)
  </behavior>
  <action>
**Step 1: Create test file** `tests/test_golden_retry.py`

Write tests that mock the following:
- `datetime.now()` — control time to simulate golden window / window closing
- `bot_state.wait_interruptible` — return False (no reboot) or True (reboot requested)
- `navigator.go_to_transfer_list` — return True (navigation success)
- `detector.scan_listings` — return ListingScanResult with varying expired_count
- `executor.relist_all` / `executor.relist_single` — return successful batch results
- `random.uniform` — return predictable wait times for assertion

Test scenarios:
1. `test_no_retry_outside_golden_window`: At 14:00, function returns (0, 0) immediately — no loop entered
2. `test_single_retry_clears_all`: At 16:10, first scan has 3 expired, second scan has 0 expired → returns accumulated (3, 0)
3. `test_multiple_retries_needed`: At 16:10, scan sequence: 5 expired → 3 expired → 0 expired → returns (5+3, 0)
4. `test_golden_window_closes_mid_retry`: At 16:10, scan has expired but next `datetime.now()` shows 16:12 (window closed) → exits with whatever was relisted, logs that items may still need relist
5. `test_reboot_interrupts_wait`: At 16:10, `wait_interruptible` returns True → function returns immediately with (0, 0) and the caller handles reboot
6. `test_navigation_failure_stops_retry`: `navigate_with_retry` returns False → stops retrying, returns accumulated stats
7. `test_per_listing_mode_uses_relist_single`: When `executor.relist_mode == "per_listing"`, uses the per-listing path instead of `relist_all`
8. `test_session_recovery_on_invalid_session`: When `executor.check_session_valid()` returns False and session recovery returns True (needs `continue`), the function exits the retry loop

**Step 2: Implement `_golden_retry_relist` in main.py**

Add the function AFTER the existing `_compute_next_wait` function (around line 483) and BEFORE `_active_wait_with_heartbeat`. This keeps helper functions grouped.

```python
def _golden_retry_relist(
    executor,
    detector,
    navigator,
    page,
    bot_state: BotState,
    auth,
    config: dict,
    fifa_logger: logging.Logger,
    initial_succeeded: int = 0,
    initial_failed: int = 0,
) -> tuple[int, int, bool]:
    """Retry relist during golden window for Processing items.

    After an initial relist, EA may still have items in "Processing..." state.
    This helper loops: wait → navigate → fresh scan → relist remaining, until
    all items are relisted or the golden window closes.

    Args:
        executor: RelistExecutor instance.
        detector: ListingDetector instance.
        navigator: TransferMarketNavigator instance.
        page: Playwright Page object.
        bot_state: BotState for interruptible waits.
        auth: AuthManager for session recovery.
        config: Config dict.
        fifa_logger: Logger for FIFA actions.
        initial_succeeded: Succeeded count from the initial relist (for logging).
        initial_failed: Failed count from the initial relist (for logging).

    Returns:
        (total_succeeded, total_failed, should_continue):
        - total_succeeded: items relisted in this retry loop (NOT including initial)
        - total_failed: items that failed in this retry loop
        - should_continue: True if the main loop should `continue` (session lost / reboot)
    """
    retry_succeeded = 0
    retry_failed = 0

    if not is_in_golden_window(datetime.now()):
        return (0, 0, False)

    fifa_logger.info(
        f"[Golden Retry] Inizio ciclo retry per ritardatari/Processing items. "
        f"Initial: {initial_succeeded} successi, {initial_failed} falliti."
    )

    while is_in_golden_window(datetime.now()):
        # Wait 5-10s (random, interruptible by Telegram)
        wait_secs = random.uniform(5, 10)
        fifa_logger.info(f"[Golden Retry] Attesa {wait_secs:.1f}s prima del rescan...")

        if bot_state.wait_interruptible(wait_secs):
            fifa_logger.info("[Golden Retry] Reboot richiesto durante attesa — esco.")
            return (retry_succeeded, retry_failed, True)

        # Navigate back to Transfer List (page may have changed after relist)
        if not navigate_with_retry(navigator, page):
            fifa_logger.warning("[Golden Retry] Navigazione fallita — esco dal retry.")
            break

        # Fresh scan — critical: must not use stale data
        scan = detector.scan_listings()

        if scan.expired_count == 0:
            fifa_logger.info("[Golden Retry] Tutti gli item sono stati relistati! Uscita dal retry.")
            break

        # Relist remaining expired/processing items
        fifa_logger.info(f"[Golden Retry] Trovati {scan.expired_count} item scaduti/processing. Rilisto...")

        if executor.relist_mode == "all":
            batch = executor.relist_all(count=scan.expired_count)
            succeeded = batch.succeeded
            failed = batch.total - batch.succeeded
            if batch.relist_error:
                fifa_logger.error(f"[Golden Retry] ERRORE RELIST: {batch.relist_error}")
                _save_error_screenshot(page, fifa_logger)
                if _handle_session_recovery(executor, auth, config, page, fifa_logger):
                    return (retry_succeeded, retry_failed, True)
        else:
            expired = [l for l in scan.listings if l.needs_relist]
            succeeded, failed = relist_expired_listings(executor, expired)

        retry_succeeded += succeeded
        retry_failed += failed
        fifa_logger.info(
            f"[Golden Retry] Relist completato: {succeeded} successi, {failed} falliti. "
            f"Totale retry: {retry_succeeded}/{retry_failed}."
        )

    # Log exit reason
    if not is_in_golden_window(datetime.now()):
        fifa_logger.info(
            f"[Golden Retry] Finestra golden chiusa. Alcuni item potrebbero "
            f"aver bisogno di relist nel prossimo ciclo normale. "
            f"Totale retry: {retry_succeeded} successi, {retry_failed} falliti."
        )

    return (retry_succeeded, retry_failed, False)
```

**Key design decisions (per locked decisions):**
1. Loop continues ONLY while `is_in_golden_window()` is True (D-01: cap is golden window)
2. Wait is `random.uniform(5, 10)` via `bot_state.wait_interruptible()` (D-02: 5-10s random, interruptible)
3. Only activates during golden window — the `if not is_in_golden_window()` guard at the top ensures this (D-03: no retry outside golden)
4. Each retry does a fresh `detector.scan_listings()` (D-04: fresh scan, not stale)
5. Does NOT modify any golden hour functions (AGENTS.md rule)
6. The `should_continue` return flag lets the main loop handle reboot/session loss without the helper knowing about the main loop structure

**IMPORTANT: The `else` fallback rule.** This helper does NOT modify the existing relist block's `if/else` structure. It's called AFTER the relist succeeds, as an addition. The existing `else` block for normal relist remains untouched.
  </action>
  <verify>
    <automated>python -m pytest tests/test_golden_retry.py -v</automated>
  </verify>
  <done>All 7+ unit tests pass. _golden_retry_relist function exists in main.py with correct signature. Function only enters loop during golden window, uses fresh scans, waits 5-10s interruptibly, and exits cleanly on golden window close / reboot / navigation failure.</done>
</task>

<task type="auto">
  <name>Task 2: Integrate helper into main loop + verify all tests pass</name>
  <files>main.py</files>
  <action>
Integrate `_golden_retry_relist` into the main loop's relist block (around lines 882-906 in main.py).

**Where to insert:** After the initial relist succeeds inside the `else` block (line 882), specifically after the `fifa_logger.info(f"Relist completato: {succeeded} successi, {failed} falliti.")` line (line 902). The retry loop should only trigger when we're in a golden window.

**Insert this block after line 902 (`fifa_logger.info(f"Relist completato: ...")`) and before line 903 (`bot_state.update_stats(...)`):**

```python
                    # --- GOLDEN RETRY: relist ritardatari/Processing durante golden window ---
                    now_retry = datetime.now()
                    if is_in_golden_window(now_retry) and succeeded > 0:
                        retry_succeeded, retry_failed, should_continue = _golden_retry_relist(
                            executor=executor,
                            detector=detector,
                            navigator=navigator,
                            page=page,
                            bot_state=bot_state,
                            auth=auth,
                            config=config,
                            fifa_logger=fifa_logger,
                            initial_succeeded=succeeded,
                            initial_failed=failed,
                        )
                        succeeded += retry_succeeded
                        failed += retry_failed
                        if should_continue:
                            continue
```

**Why this placement works:**
1. It's INSIDE the `else` block (normal relist path), after relist succeeds — the existing `else` fallback for normal relist is preserved (AGENTS.md rule)
2. It only triggers when `is_in_golden_window()` is True AND there were successful relists — no retry outside golden hours (D-03)
3. The `succeeded += retry_succeeded` accumulates retry stats into the cycle stats before `bot_state.update_stats()` and notification logic see them
4. The `if should_continue: continue` handles the session recovery / reboot signal from the helper

**CRITICAL: Verify the else-fallback structure remains intact.** After integration, the relist block structure MUST still be:

```python
if scan.expired_count > 0:
    in_hold = is_in_hold_window(datetime.now())
    force_relist = bot_state.consume_force_relist()
    if in_hold and not force_relist:
        # HOLD block
        ...
    else:
        # RELIST block (normal + golden + force)
        ...
        # [NEW: golden retry block here]
    # [end of if/else — both branches handled]
else:
    # No expired items block
    ...
```

The `else` fallback for normal relist is the outer `else` at line 882. The new code goes INSIDE this else, after the initial relist. No structural change to the if/else chain.

**Also add the import** for `_golden_retry_relist` in `tests/test_golden_timeline.py` if needed (it's already in main.py so it's importable from there).

**Run ALL tests to verify nothing is broken:**
```bash
python -m pytest tests/ -v
```
  </action>
  <verify>
    <automated>python -m pytest tests/ -v</automated>
  </verify>
  <done>Golden retry helper is integrated into the main loop. ALL existing tests (including test_golden_timeline.py, test_bot_state.py, test_relist.py, etc.) still pass. The else-fallback for normal relist is preserved. The retry loop only activates during golden window after a successful relist.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Main loop → retry helper | Internal function call, no untrusted input |
| Retry helper → Playwright DOM | DOM state may change between retries (expected) |
| Retry helper → Telegram | wait_interruptible may be interrupted by reboot |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-gpr-01 | Tampering | DOM scan data | accept | Fresh scan each retry prevents stale data; no user input involved |
| T-gpr-02 | Denial of Service | Retry loop duration | mitigate | Loop capped by `is_in_golden_window()` (max ~2 min window); 5-10s wait between iterations |
| T-gpr-03 | Elevation of Privilege | Reboot during retry | mitigate | `wait_interruptible` returns True on reboot; `should_continue` propagates to main loop |
</threat_model>

<verification>
1. `python -m pytest tests/test_golden_retry.py -v` — New tests pass
2. `python -m pytest tests/ -v` — All existing tests still pass
3. Verify the else-fallback structure in main.py is preserved (grep for the pattern)
4. Verify `_golden_retry_relist` is called only when `is_in_golden_window()` is True
</verification>

<success_criteria>
- `_golden_retry_relist` function exists in main.py with correct signature
- Function only enters retry loop during golden window (:09-:11)
- Each retry waits 5-10s (random) via `bot_state.wait_interruptible()`
- Each retry does a FRESH `detector.scan_listings()` call
- Loop exits when: all items relisted (expired_count == 0), golden window closes, reboot requested, or navigation fails
- The existing else-fallback for normal relist is preserved (AGENTS.md rule)
- No golden hour functions are modified (AGENTS.md rule)
- All tests pass (new + existing)
</success_criteria>

<output>
After completion, create `.planning/quick/golden-processing-retry/golden-processing-retry-01-SUMMARY.md`
</output>

---
phase: quick-fix-v2-integration
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - v2_relist_logic.py
  - main.py
autonomous: true
requirements:
  - RELIST-01
  - LOG-03

must_haves:
  truths:
    - "Pass 2 ALWAYS executes if we're in the sync minute (never skipped by late arrival)"
    - "A log message explains why Pass 2 was skipped when outside the sync minute"
    - "main.py loop calls implementazione_nuova_logica() instead of 270+ lines of polling logic"
    - "Single consolidated Telegram notification after both passes complete"
    - "next_wait is returned from the function and used for the sleep at cycle end"
    - "Per-item action logging still works (via relist_expired_listings callback)"
  artifacts:
    - path: "v2_relist_logic.py"
      provides: "Two-pass batch relist logic"
      exports: ["implementazione_nuova_logica"]
    - path: "main.py"
      provides: "Main loop with integrated v2 logic"
      contains: "implementazione_nuova_logica("
  key_links:
    - from: "main.py:289-616"
      to: "v2_relist_logic.py::implementazione_nuova_logica()"
      via: "function call replacing polling block"
      pattern: "implementazione_nuova_logica\\("
    - from: "v2_relist_logic.py:28,78"
      to: "main.py::relist_expired_listings()"
      via: "callback parameter"
      pattern: "relist_expired_listings"
    - from: "v2_relist_logic.py"
      to: "main.py:617-619"
      via: "returned next_wait value"
      pattern: "next_wait = implementazione"
---

<objective>
Fix 2 bugs in v2_relist_logic.py and integrate the two-pass batch architecture into main.py, replacing 270+ lines of polling logic.

Purpose: The current main.py has a complex polling system with hard stop at :45 that misses items expiring between :45-:59. The two-pass batch approach (Pass 1 at :00, sleep, Pass 2 at :40) eliminates this gap while drastically simplifying the code.

Output: Bug-fixed v2_relist_logic.py integrated into main.py as a single function call replacing lines 289-616.
</objective>

<execution_context>
@C:/Users/Ebby/.config/opencode/get-shit-done/workflows/execute-plan.md
@C:/Users/Ebby/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@C:/App/fifa-relist/v2_relist_logic.py
@C:/App/fifa-relist/main.py
@C:/App/fifa-relist/thinking.md

## Key Interfaces

From main.py — functions/utilities that remain and are used by or alongside v2:
```python
# Lines 186-209: Per-item relist with action logging (KEEP — passed as callback)
def relist_expired_listings(executor, expired_listings) -> tuple[int, int]:
    # Logs each action via action_logger, returns (succeeded, failed)

# Lines 62-70: Status table for rich console (KEEP — passed as param)
def make_status_table(phase: str, scanned: int, relisted: int, errors: int) -> Table:

# Lines 272-275: Navigation with retry (KEEP — called before v2 function)
def navigate_with_retry(navigator, page) -> bool:
```

From v2_relist_logic.py — current function signature (needs relist_expired_listings added):
```python
def implementazione_nuova_logica(page, detector, executor, app_config, cycle, status_console, make_status_table):
    # Returns: next_wait (int, seconds until next cycle)
```

## Integration Target (main.py)

Current structure in the `while True` loop (lines 257-619):
```
257: while True:
261:     ensure_session(...)
264:     console check + continue
272:     navigate_with_retry(...) + continue on fail
277:     pre-navigation (precision wait to sync minute)
289:     scan_result = detector.scan_listings()     ← DELETE
290-616: 270+ lines of polling/notification/wait  ← DELETE (replaced by v2 call)
617:     logger.info(...)                           ← KEEP
618:     rate_limiter.wait()                        ← KEEP
619:     time.sleep(next_wait)                      ← KEEP (next_wait from v2)
```

After integration:
```
257: while True:
261:     ensure_session(...)
264:     console check + continue
272:     navigate_with_retry(...) + continue on fail
277:     pre-navigation (precision wait to sync minute)
289:     next_wait = implementazione_nuova_logica(...)  ← NEW (single call)
617:     logger.info(...)                               ← KEEP
618:     rate_limiter.wait()                            ← KEEP
619:     time.sleep(next_wait)                          ← KEEP
```
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix bugs + add callback param in v2_relist_logic.py</name>
  <files>v2_relist_logic.py</files>
  <action>
Three changes to v2_relist_logic.py:

**Bug 1 fix (line 42):** Change the Pass 2 entry condition so Pass 2 ALWAYS runs when in the sync minute. Currently:
```python
if now.minute == sync_minute and now.second < 40:
```
This skips Pass 2 if we arrive after :40 (e.g., Pass 1 finishes at :10:45). Fix:
```python
if now.minute == sync_minute:
    if now.second < 40:
        wait_seconds = 40 - now.second
        logger.info(f"Pausa silenziosa di {wait_seconds}s fino al secondo :40...")
        time.sleep(wait_seconds)
    # Pass 2 always executes if we're in the sync minute
```
Move lines 48-84 (Pass 2 logic) OUTSIDE the `if now.second < 40:` block but INSIDE the `if now.minute == sync_minute:` block.

**Bug 2 fix (add else after line 39):** After `if sync_minute is not None:` block (line 39), add an else clause:
```python
else:
    logger.warning("Pass 2 saltato: sync_minute_offset non configurato.")
```
Also add an else when `now.minute != sync_minute`:
```python
else:
    logger.info(f"Pass 2 saltato: minuto corrente {now.minute} != sync_minute {sync_minute}.")
```

**Add callback parameter (line 8):** Add `relist_expired_listings` to the function signature. This avoids circular imports (main.py imports v2, can't have v2 import main). Change:
```python
def implementazione_nuova_logica(page, detector, executor, app_config, cycle, status_console, make_status_table):
```
to:
```python
def implementazione_nuova_logica(page, detector, executor, app_config, cycle, status_console, make_status_table, relist_expired_listings):
```

Then remove `# type: ignore` from lines 28 and 78 since the function is now a real parameter.
  </action>
  <verify>
<automated>python -c "import v2_relist_logic; import inspect; sig = inspect.signature(v2_relist_logic.implementazione_nuova_logica); print('Params:', list(sig.parameters.keys())); assert 'relist_expired_listings' in sig.parameters, 'Missing callback param'"</automated>
  </verify>
  <done>
- Bug 1: Pass 2 always executes when in sync_minute regardless of current second
- Bug 2: Log messages explain when/why Pass 2 is skipped
- Function accepts relist_expired_listings as callback parameter
- File imports cleanly without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Integrate v2 into main.py (replace polling block)</name>
  <files>main.py</files>
  <action>
Replace the massive polling block in main.py's `while True` loop with a single call to `implementazione_nuova_logica()`.

**Step 1:** Add import at top of main.py (after existing imports, near line 28):
```python
from v2_relist_logic import implementazione_nuova_logica
```

**Step 2:** Delete lines 289-616 in main.py (from `scan_result = detector.scan_listings()` through the end of the `else: # Calcolo attesa dinamica` block). This is the entire scan→poll→notify→wait block.

**Step 3:** Insert the v2 function call in its place:
```python
            next_wait = implementazione_nuova_logica(
                page, detector, executor, app_config,
                cycle, status_console, make_status_table,
                relist_expired_listings,
            )
```

**What stays unchanged:**
- Lines 257-275: while loop header, ensure_session, console check, navigate_with_retry
- Lines 277-287: pre-navigation precision wait
- Lines 617-619: logger.info, rate_limiter.wait(), time.sleep(next_wait)
- Lines 621-716: exception handlers, CLI, etc.

**What is removed:** ~327 lines of polling/notification/wait calculation logic.
  </action>
  <verify>
<automated>python -c "import ast; tree = ast.parse(open('main.py').read()); print('Syntax OK'); lines = open('main.py').readlines(); v2_calls = [i+1 for i,l in enumerate(lines) if 'implementazione_nuova_logica(' in l]; print(f'v2 calls at lines: {v2_calls}'); assert len(v2_calls) >= 1, 'Missing v2 integration call'"</automated>
  </verify>
  <done>
- main.py imports implementazione_nuova_logica from v2_relist_logic
- Lines 289-616 (polling block) replaced with single function call
- Function receives all required params including relist_expired_listings callback
- next_wait returned from function feeds into existing sleep at line 619
- main.py has no syntax errors
- No polling logic, post-relist polling, or per-cycle Telegram notification code remains in main.py's while loop
  </done>
</task>

</tasks>

<verification>
After both tasks:
1. `python -c "import main; import v2_relist_logic"` — both files import cleanly
2. `python main.py config show` — CLI still works (integration doesn't break CLI)
3. Grep for "poll_round" in main.py — should return 0 matches (polling removed)
4. Grep for "implementazione_nuova_logica" in main.py — should show import + call
5. Line count: main.py should drop from ~716 to ~400 lines
</verification>

<success_criteria>
- v2_relist_logic.py: Bug 1 fixed (Pass 2 always runs in sync minute), Bug 2 fixed (else logging added), callback param added
- main.py: 270+ lines of polling replaced with single function call
- Both files import without errors
- relist_expired_listings callback preserves per-item action logging
- Single consolidated Telegram notification (handled inside v2 function)
- next_wait flows correctly from v2 return → sleep at cycle end
</success_criteria>

<output>
After completion, create `.planning/quick/1-fix-2-bugs-v2-relist-logic-integra-in-ma/quick-fix-v2-integration-1-SUMMARY.md`
</output>

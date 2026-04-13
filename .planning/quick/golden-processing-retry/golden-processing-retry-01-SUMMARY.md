---
phase: golden-processing-retry
plan: 01
subsystem: golden-hour-relist
tags: [golden-hour, retry-loop, processing-items, tdd]
dependency_graph:
  requires: [main.py, models/listing.py, bot_state.py]
  provides: [_golden_retry_relist helper]
  affects: [main.py relist block]
tech_stack:
  added: [random.uniform for 5-10s retry wait]
  patterns: [TDD red-green, helper extraction, interruptible wait]
key_files:
  created:
    - tests/test_golden_retry.py
  modified:
    - main.py
decisions:
  - D-01: Loop capped by is_in_golden_window() (max ~2 min window)
  - D-02: 5-10s random wait via bot_state.wait_interruptible()
  - D-03: Only activates during golden window — guard check at function entry
  - D-04: Fresh scan each retry via detector.scan_listings()
  - D-05: Returns should_continue flag for clean main loop integration
metrics:
  duration: 8m
  completed: 2026-04-13
  tasks: 2
  files: 2
---

# Phase golden-processing-retry Plan 01: Golden Processing Retry Summary

Golden hour retry loop for Processing items: `_golden_retry_relist()` helper with 5-10s interruptible waits and fresh scans until all items are relisted or golden window closes.

## Changes Made

### Task 1: Create `_golden_retry_relist` helper + unit tests (TDD)
- **Commit:** `b9fc754`
- Added `_golden_retry_relist()` function in `main.py` (after `_compute_next_wait`, before `_active_wait_with_heartbeat`)
- Function signature: `_golden_retry_relist(executor, detector, navigator, page, bot_state, auth, config, fifa_logger, initial_succeeded=0, initial_failed=0) -> tuple[int, int, bool]`
- Returns `(retry_succeeded, retry_failed, should_continue)` — clean separation from main loop
- 10 unit tests in `tests/test_golden_retry.py` covering:
  1. No retry outside golden window
  2. Single retry clears all expired items
  3. Multiple retries needed (5→3→0 expired)
  4. Golden window closes mid-retry
  5. Reboot interrupts wait
  6. Navigation failure stops retry
  7. Per-listing mode uses `relist_expired_listings`
  8. Session recovery triggers exit
  9. Wait timing uses `random.uniform(5, 10)`
  10. Fresh scan each iteration

### Task 2: Integrate helper into main loop
- **Commit:** `1f60c59`
- Inserted golden retry call after initial relist in the `else` block (line ~1004-1024)
- Only triggers when `is_in_golden_window()` AND `succeeded > 0`
- Accumulates retry stats before `bot_state.update_stats()` sees them
- `should_continue` flag handled with `continue` in main loop
- Else-fallback for normal relist preserved ✅
- All 658 tests pass ✅

## Deviations from Plan

None — plan executed exactly as written.

## Key Design Decisions

1. **Loop cap = golden window** (D-01): The `while is_in_golden_window()` condition naturally limits retries to the :09-:11 window (~2 min max)
2. **5-10s random wait** (D-02): Uses `random.uniform(5, 10)` via `bot_state.wait_interruptible()` for Telegram responsiveness
3. **Fresh scan each retry** (D-04): `detector.scan_listings()` called inside loop — never uses stale scan data
4. **should_continue flag** (D-05): Clean return value lets main loop handle reboot/session loss without the helper knowing about the outer loop structure

## AGENTS.md Compliance

- ✅ No golden hour functions modified (`get_next_golden_hour`, `is_in_golden_period`, `is_in_hold_window`, `is_in_golden_window`)
- ✅ Else-fallback for normal relist preserved
- ✅ Rate limiting maintained (5-10s between retries)
- ✅ `wait_interruptible` used (not `time.sleep`) for Telegram responsiveness

## Self-Check: PASSED

- main.py: FOUND
- tests/test_golden_retry.py: FOUND
- golden-processing-retry-01-SUMMARY.md: FOUND
- Commit b9fc754: FOUND
- Commit 1f60c59: FOUND
- All 658 tests pass

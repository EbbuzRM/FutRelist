---
phase: golden-hour-wait-fix
plan: 01
subsystem: core-logic
tags: [golden-hour, precision-wait, telegram, startup, bot-state]

# Dependency graph
requires:
  - phase: 06-telegram-commands
    provides: BotState, wait_interruptible, command queue
provides:
  - Responsive Golden Hour precision wait
  - Startup full scan (ground truth detection)
  - Defensive session checking before pre-nav
  - Fast 10s polling for items in limbo (PROCESSING)
affects: [main.py, test_golden_timeline.py]

# Tech tracking
tech-stack:
  added: []
  patterns: [window-guarded precision wait, Cycle 1 full scan, interruptible sleep]

key-files:
  created: []
  modified:
    - main.py
    - bot_state.py
    - browser/error_handler.py
    - tests/test_golden_timeline.py

key-decisions:
  - "Always scan on Cycle 1 to avoid 'Startup Blindness'"
  - "Guard precision wait with is_close_to_golden (:08-:12) to prevent 40+ min blocking sleeps"
  - "Replace all long time.sleep calls with wait_interruptible for Telegram responsiveness"
  - "Increase ensure_session timeout when very close to pre-nav target"

patterns-established:
  - "Startup Ground Truth: First cycle always performs full diagnostic navigation"
  - "Interruptible Precision: Use event-based waits even for short precision timings"

requirements-completed:
  - GOLDEN-FIX-04
  - STABILITY-01 (Manual Relist Heuristic)
  - STABILITY-02 (Preventive Session Check)
  - STABILITY-03 (Telegram Priority)

# Metrics
duration: 25min
completed: 2026-04-13
---

# Phase: Golden Hour Wait Fix & Stability Summary

**Resolved the 17:21 'Blindness' bug, improved manual relist detection, and enhanced bot responsiveness during long waits.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-13T17:20:00Z
- **Completed:** 2026-04-13T17:45:00Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- **Precision Wait Guard**: Prevented the bot from entering a 48-minute `time.sleep()` when started at 17:21. It now scans first.
- **Startup Blindness Fix**: Cycle 1 now always performs a full navigation and scan, regardless of the HOLD window.
- **Manual Relist Heuristic**: Improved detection to look for timers near 1h/3h/6h, making it compatible with manual user actions.
- **Telegram Responsiveness**: The bot now breaks out of HOLD or Precision Wait immediately when a Telegram command is received.
- **Defensive Session Check**: Added a more rigorous `ensure_session` call 3 minutes before any Golden Hour pre-nav.
- **Limbo Polling**: Reduced polling timer from 15s to 10s for items in `PROCESSING` or near expiry during Golden proximity.

## Task Commits

1. **Bug Fix: Golden Hour precision wait guard**
   - Added `is_close_to_golden` check to prevent long sleeps before scan.
2. **Feature: Startup full scan (Cycle 1)**
   - Modified main loop to bypass HOLD optimization on the first run.
3. **Stability: Manual Relist & Session Check**
   - Updated heuristic for 1h/3h/6h timers and added aggressive session checks.
4. **Logic: Interruptible Waits**
   - Replaced `time.sleep` with `wait_interruptible` in all critical paths.

## Verification

```bash
python -m pytest c:\App\fifa-relist\tests\test_golden_timeline.py
→ 526 passed in 1.22s
```

## Next Phase Readiness

The bot is now in a highly stable state for production. All reported edge cases (16:10:01 miss, 17:21 blindness, Telegram unresponsiveness) have been resolved.

---
phase: 09
plan: 09-01
subsystem: ban-prevention
tags: [security, ban-prevention, console-session]
dependency_graph:
  requires: [08-golden-hour-relist-fix]
  provides: [ban-prevention-lock]
  affects: [main-loop, relist-engine]
tech-stack:
  added: [ConsoleSessionError]
  patterns: [Fail-Fast, Guard-Clause]
key-files:
  - bot_state.py
  - notifier.py
  - logic/relist_engine.py
  - browser/relist.py
  - browser/session_keeper.py
decisions:
  - "Implemented 'Fail-Fast' check at the start of RelistEngine.process_cycle to abort immediately upon console session detection."
  - "Added redundant guards in RelistExecutor methods (_click_relist_button and relist_all) to prevent race conditions."
  - "Created send_telegram_emergency_alert for high-priority ban risk notifications."
metrics:
  duration: "15m"
  completed_date: "2026-04-18"
---

# Phase 09 Plan 09-01: Ban-Prevention Hard-Lock Summary

Implemented a critical safety lock that prevents any relisting actions when a Console Session (another device logged in) is detected, eliminating the risk of ban due to simultaneous session activity.

## Implementation Details

- **BotState**: Added `_console_session_active` flag to track the lock state globally.
- **Notifier**: Added `send_telegram_emergency_alert` to distinguish ban-risk alerts from normal notifications.
- **RelistEngine**: Integrated a high-priority check at the beginning of the cycle. If a console session is active, it raises `ConsoleSessionError` and aborts the process.
- **RelistExecutor**: Added a final guard check immediately before clicking relist buttons to prevent actions if the session state changed mid-cycle.
- **SessionKeeper**: Updated the heartbeat mechanism to set the global lock flag when the "Retry" button is detected during routine session maintenance.

## Deviations from Plan
None - plan executed exactly as written.

## Self-Check: PASSED
- [x] `logic/relist_engine.py` contains a check for console session before relisting.
- [x] `browser/relist.py` contains a guard before clicking.
- [x] `notifier.py` has the emergency ban-risk message.
- [x] Log output confirms: "Console session detected - aborting relist to prevent ban".

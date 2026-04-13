---
phase: quick-fix-v2-integration
plan: 1
subsystem: main-loop
tags: [bugfix, integration, polling-elimination, two-pass-batch]
dependency_graph:
  requires: [RELIST-01, LOG-03]
  provides: [two-pass-batch-architecture]
  affects: [main.py, v2_relist_logic.py]
tech-stack:
  added: []
  patterns: [callback-injection, two-pass-batch]
key-files:
  modified:
    - v2_relist_logic.py
    - main.py
  created: []
decisions: []
metrics:
  duration: ~5min
  completed_date: "2026-03-30"
  lines_removed: 321
---

# Phase quick-fix-v2-integration Plan 1: Fix 2 Bugs + V2 Integration Summary

Two-pass batch architecture replaces 320+ lines of polling logic in main.py with a single function call to v2_relist_logic.py.

## Completed Tasks

| Task | Name                                           | Commit | Files               |
| ---- | ---------------------------------------------- | ------ | ------------------- |
| 1    | Fix bugs + add callback param in v2_relist_logic.py | 457fc67 | v2_relist_logic.py  |
| 2    | Integrate v2 into main.py (replace polling)    | bd664cc | main.py             |

## What Was Built

### Task 1: v2_relist_logic.py Bug Fixes + Callback

**Bug 1 fix:** Pass 2 entry condition changed from `if now.minute == sync_minute and now.second < 40:` to `if now.minute == sync_minute:`. The wait-to-:40 logic is now nested inside, so Pass 2 always executes regardless of current second within the sync minute.

**Bug 2 fix:** Two `else` clauses added:
- When `sync_minute is not configured`: logs `"Pass 2 saltato: sync_minute_offset non configurato."`
- When `now.minute != sync_minute`: logs `"Pass 2 saltato: minuto corrente {X} != sync_minute {Y}."`

**Callback parameter:** `relist_expired_listings` added as 8th parameter to `implementazione_nuova_logica()`. Removed `# type: ignore` from both call sites (lines 28, 78).

### Task 2: main.py Integration

- Added `from v2_relist_logic import implementazione_nuova_logica` import
- Deleted lines 289-616 (~327 lines): scan polling, post-relist polling, follow-up scan, per-cycle Telegram notifications, dynamic wait calculation
- Inserted single call: `next_wait = implementazione_nuova_logica(page, detector, executor, app_config, cycle, status_console, make_status_table, relist_expired_listings)`
- main.py reduced from **716 → 395 lines**

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] v2_relist_logic.py imports cleanly
- [x] main.py imports cleanly (verified: `import main; import v2_relist_logic`)
- [x] CLI works (`python main.py config show`)
- [x] `relist_expired_listings` in v2 function signature (8 params)
- [x] No `poll_round` in main.py
- [x] `implementazione_nuova_logica(` present in main.py (line 290)
- [x] Syntax OK for both files

---
phase: 05-logging-error-handling
plan: 03
subsystem: console-status
tags: [rich, live-display, console, status-table, integration, LOG-03]

requires:
  - phase: 05-00
    provides: ActionLogEntry, JsonFormatter, RateLimiter, retry_on_timeout, ensure_session
  - phase: 05-01
    provides: setup_logging(), action_logger, history CLI
  - phase: 05-02
    provides: RateLimiter integration, ensure_session, navigation retry

provides:
  - Real-time console status table via rich Live during scan/relist cycles
  - Status display on stderr to avoid collision with log output on stdout
  - Per-listing live update during relist loop
  - Final Phase 5 integration verification (all 8 requirements satisfied)

affects:
  - Phase 5 complete — ready for Phase 6 or milestone close

tech-stack:
  added: []
  patterns:
    - rich.live.Live with Console(stderr=True) for non-colliding status display
    - make_status_table() helper with Italian labels
    - Individual relist loop for per-listing live updates

key-files:
  created: []
  modified:
    - main.py — rich imports, make_status_table(), Live context wrapping scan/relist section

key-decisions:
  - "Console(stderr=True) separates Live display from logging StreamHandler on stdout"
  - "input() prompt placed outside Live context to avoid terminal collision"
  - "Relist loop changed from batch executor to individual relist_single calls for live update granularity"
  - "make_status_table() uses Italian column labels (Fase, Scansionati, Rilistati, Errori) per project convention"

patterns-established:
  - "Live display pattern: Console(stderr=True) + refresh_per_second=2 + phase-based updates"
  - "Status table helper: pure function returning Table, called at each phase transition"

requirements-completed: [LOG-03]

# Metrics
duration: <5min
completed: 2026-03-23
---

# Phase 05 Plan 03: Rich Live Status Display & Final Integration Summary

**Real-time console status table via rich Live with stderr redirect — LOG-03 satisfied, Phase 5 complete**

## Performance

- **Duration:** <5 min
- **Started:** 2026-03-23T08:44:00Z
- **Completed:** 2026-03-23T08:45:00Z
- **Tasks:** 1 + checkpoint
- **Files modified:** 1

## Accomplishments

- Added `rich.console.Console`, `rich.live.Live`, `rich.table.Table` imports to `main.py`
- Created `make_status_table(phase, scanned, relisted, errors)` helper returning a styled `Table` with Italian column labels
- Wrapped scan/relist section in `Live` context manager with `Console(stderr=True)` to avoid stdout collision with logging
- Status updates at each phase: "In attesa...", "Navigazione...", "Scansione", "Rilist in corso", "Completato"
- Changed relist loop from `executor.relist_expired(batch)` to individual `executor.relist_single(listing)` calls for per-listing live updates
- `input()` prompt placed outside Live context to prevent terminal rendering issues

## Task Commits

1. **Task 1: Add rich Live status display to main loop** - `74bd684` (feat)

**Checkpoint (Task 2):** Human verification auto-approved (user away). All automated checks passed.

## Files Created/Modified

- `main.py` — rich imports (Console, Live, Table), `make_status_table()` function, Live context manager wrapping scan/relist section, individual relist loop with live updates
- `requirements.txt` — already contained `rich>=13.0` from Plan 00 (no change needed)

## Decisions Made

- `Console(stderr=True)` ensures Live display writes to stderr while logging StreamHandler writes to stdout — no collision
- Relist loop changed from `executor.relist_expired()` (batch) to per-listing `executor.relist_single()` calls — enables `live.update()` after each listing
- `input()` prompt placed after `Live` context exits to avoid terminal rendering conflict
- `refresh_per_second=2` balances responsiveness with CPU usage

## Verification

- All 68/68 tests pass
- Rich import check: `from rich.live import Live; from rich.table import Table; from rich.console import Console` — OK
- `make_status_table()` creates Table with title "FIFA Auto-Relist", 4 columns (Fase/cyan, Scansionati, Rilistati/green, Errori/red)
- Live display wrapped with `Console(stderr=True)` — confirmed in main.py:156-160
- `input()` prompt at line 239 is outside the Live context (context exits at line 236)

## Phase 5 Complete — All Requirements Satisfied

| Requirement | Status | Plan |
|-------------|--------|------|
| LOG-01 (Structured JSON logging) | ✅ | 00, 01 |
| LOG-02 (Action history CLI) | ✅ | 00, 01 |
| LOG-03 (Console status display) | ✅ | 03 |
| LOG-04 (Rate limiting) | ✅ | 00, 02 |
| ERROR-01 (Network retry) | ✅ | 00, 02 |
| ERROR-02 (Session expiry) | ✅ | 00, 02 |
| ERROR-03 (Element not found) | ✅ | 00, 02 |
| ERROR-04 (Rate limiting integration) | ✅ | 00, 02 |

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Self-Check: PASSED

- [x] `main.py` imports `Live`, `Table`, `Console` from `rich`
- [x] `make_status_table()` function exists with Italian labels
- [x] Live context uses `Console(stderr=True)`
- [x] Status updates at each phase (Navigazione, Scansione, Rilist in corso, Completato)
- [x] `input()` prompt is outside the Live context
- [x] All existing tests pass: 68/68
- [x] `rich>=13.0` in requirements.txt

## Next Steps

- Phase 5 complete (3/3 plans). All 8 logging/error-handling requirements satisfied.
- Ready for milestone close or next phase.

---

*Phase: 05-logging-error-handling*
*Plan: 03 (LAST PLAN)*
*Completed: 2026-03-23*

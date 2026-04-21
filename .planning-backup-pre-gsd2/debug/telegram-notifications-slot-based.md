---
status: verified
trigger: "Le notifiche Telegram non vengono inviate durante le golden hours. L'accumulator cresce (31→62→93) ma non viene mai flushato."
created: 2026-04-15T12:00:00
updated: 2026-04-16T18:33:00
---

## Current Focus

hypothesis: CONFIRMED — Notification block skipped when current cycle has 0 relists, orphaning accumulated notifications
test: Applied work-slot-finished fix, all 658 tests pass
expecting: Notification fires when bot finishes work and goes to sleep (next_wait >= 120s)
next_action: Wait for human verification at next golden hour cycle

## Symptoms

expected: Bot sends Telegram notification after each golden hour relist, before going to sleep for ~58 min
actual: Accumulator keeps growing (31→62→93 across 3 golden hours) but notification NEVER sent
errors: No error messages — silent bug
reproduction: Observe logs from 16:10 → 18:17 on 2026-04-16: "[Notifica] Accumulo" logged but no "Notifica Telegram inviata"
started: Since the time/threshold notification logic was introduced

## Root Cause (Confirmed 2026-04-16)

The bug has two interacting parts:

1. **Golden relist cycle** (Ciclo 8, 16:10:34): `succeeded=31`, `next_wait=10s` (ritardatari polling) → `more_items_coming = (10 <= 120 AND 1 < 5) = TRUE` → notification deferred
2. **Ritardatari scan cycle** (Ciclo 9, 16:11:01): `succeeded=0, failed=0` → Line 1230 `if succeeded > 0 or failed > 0` → **FALSE** → entire notification block SKIPPED → accumulated 31 relists are ORPHANED
3. Bot sleeps ~58 minutes until next golden hour → accumulates more → same pattern repeats

The notification dispatch was INSIDE the `if succeeded > 0 or failed > 0` block, so it could ONLY run during cycles that had relists. The ritardatari cycle (which always finds 0 expired after a golden relist) could never flush the accumulator.

## Evidence

- timestamp: 2026-04-16T18:26:00
  checked: app.log lines from 16:10 to 18:25
  found: 3 golden hour cycles (16:10, 17:11, 18:11) each log "[Notifica] Accumulo: N rilistati" but no "Notifica Telegram inviata". Accumulator grows 31→62→93.
  implication: Notification is deferred every time but never dispatched

- timestamp: 2026-04-16T18:26:00
  checked: main.py lines 1229-1269 (old notification logic)
  found: Notification dispatch at line 1265-1269 was INSIDE `if succeeded > 0 or failed > 0` block at line 1230
  implication: When ritardatari cycle has 0 relists, the deferred notification is orphaned

## Resolution

root_cause: Notification dispatch was gated behind `if succeeded > 0 or failed > 0`, making it impossible to flush accumulated notifications during cycles with no relists (ritardatari scans). Combined with `more_items_coming=True` during golden relists (next_wait=10s), notifications were always deferred but never dispatched.
fix: Moved notification dispatch logic OUTSIDE the `if succeeded > 0 or failed > 0` block. New "work-slot finished" logic: accumulate during rapid cycles (next_wait < 120s), send when bot goes to sleep (next_wait >= 120s) or after 5 rapid cycles (safety net). Removed unused NOTIFICATION_INTERVAL and NOTIFICATION_THRESHOLD constants.
verification: Python syntax check passed, 658/658 tests passed.
files_changed: [main.py]

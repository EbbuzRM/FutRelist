---
phase: golden-hour-relist-fix
verified: 2026-04-07T00:00:00Z
status: gaps_found
score: 4/6 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 6/6
  gaps_closed:
    - "Dead code branch claim corrected — elif 0 < seconds_until_golden <= 30 IS reachable (e.g. 16:09:45)"
  gaps_remaining: []
  regressions:
    - "Fix 1: post-nav wait fires outside golden period (e.g. 14:00 would wait 2h until 16:10)"
    - "Fix 2: in_golden_window ALWAYS false after golden passes (get_next_golden_hour returns NEXT golden, not current)"
    - "Fix 3: close_to_golden ALWAYS false after golden passes (same root cause as Fix 2)"
gaps:
  - truth: "After navigate_with_retry, bot waits until exactly :10:00 before scanning (prevents early relist)"
    status: partial
    reason: "Logic works correctly when in golden period (e.g. 16:09:43 waits 17s). BUT missing is_in_golden_period() guard — fires outside golden period too. At 14:00, next_golden=16:10, now<next_golden=True, would sleep 2+ hours instead of scanning immediately."
    artifacts:
      - path: "main.py"
        issue: "Lines 447-453: missing is_in_golden_period(now) guard on the post-nav wait"
    missing:
      - "Add is_in_golden_period(now) to the condition: if next_golden and now < next_golden and is_in_golden_period(now):"
  - truth: "Post-relist wait uses seconds-based window for rapid polling of stragglers"
    status: failed
    reason: "get_next_golden_hour() returns the NEXT future golden. After 16:10:00 passes, it returns 17:10:00. So at 16:10:15, secs=3585, and -60 < 3585 < 120 is False. Rapid polling NEVER triggers after the golden passes — exactly when stragglers need it most."
    artifacts:
      - path: "main.py"
        issue: "Lines 524-530: window check compares to next FUTURE golden (17:10) instead of the CURRENT one (16:10)"
    missing:
      - "Use time-based check on current hour/minute instead of get_next_golden_hour: if now_after.hour in (16,17,18) and 9 <= now_after.minute <= 12"
  - truth: "No-expired branch checks if close to golden and uses 15s polling"
    status: partial
    reason: "Works BEFORE the golden (e.g. 16:08:00 -> secs=120, close=True). FAILS AFTER the golden passes (e.g. 16:12:00 -> next_golden=17:10, secs=3480, close=False). Same root cause as Fix 2."
    artifacts:
      - path: "main.py"
        issue: "Lines 557-562: uses get_next_golden_hour which returns next future golden, not the one we just passed"
    missing:
      - "Add a check for being within N minutes AFTER the current golden, not just before the next one"
---

# Phase: Golden Hour Relist Fix — Re-Verification Report

**Phase Goal:** Fix three golden timing issues: (1) prevent early relist before :10:00, (2) fix broken post-relist wait logic, (3) add rapid polling near golden hours.
**Verified:** 2026-04-07T00:00:00Z
**Status:** gaps_found
**Re-verification:** Yes — after gap closure from previous verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After `navigate_with_retry`, bot waits until exactly :10:00 if before golden | ⚠️ PARTIAL | Lines 447-453: `if next_golden and now < next_golden` — correct for golden period, but **missing `is_in_golden_period()` guard**. At 14:00, would wait 2h+ until 16:10 instead of scanning immediately. |
| 2 | Post-relist wait uses seconds-based window (`-60 < secs < 120`) instead of broken `minute >= 10` | ✗ FAILED | Lines 524-530: Uses `get_next_golden_hour(now_after)` which returns NEXT future golden. After 16:10 passes, returns 17:10 → secs=~3585 → window check always False. **Rapid polling NEVER triggers after golden passes.** |
| 3 | "No expired" branch checks `close_to_golden` with 15s polling | ⚠️ PARTIAL | Lines 557-562: Works BEFORE golden (16:08:00 → secs=120 → close=True). FAILS after golden (16:12:00 → next_golden=17:10 → secs=3480 → close=False). Same root cause as Fix 2. |
| 4 | Golden hour functions unchanged | ✓ VERIFIED | `get_next_golden_hour` (L252-268), `is_in_golden_period` (L271-283), `is_in_hold_window` (L286-304) — identical to previous verification |
| 5 | Normal relist `else` branch still exists | ✓ VERIFIED | Line 487: `else:` with full relist logic — AGENTS.md rule satisfied |
| 6 | No unbound variables | ✓ VERIFIED | `next_wait` initialized L461=600; `succeeded`/`failed` L458-459; all branches set before use at L629 |

**Score:** 4/6 truths verified (2 partial, 1 failed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `main.py` L447-453 | Post-nav wait until :10:00 | ⚠️ PARTIAL | Correct logic, missing golden period guard |
| `main.py` L521-534 | Seconds-based post-relist window | ✗ BROKEN | Window check always fails after golden passes |
| `main.py` L557-566 | Close-to-golden rapid polling | ⚠️ PARTIAL | Only works before golden, not after |
| `main.py` L252-304 | Golden hour functions | ✓ VERIFIED | Unchanged, correct |
| `main.py` L487-551 | Normal relist else branch | ✓ VERIFIED | Present and complete |

### Key Link Verification

| From | To | Via | Status | Details |
|------|---|-----|--------|---------|
| Post-nav wait (L447) | `get_next_golden_hour` | called at L449 | ⚠️ PARTIAL | Returns NEXT golden, not current — causes over-waiting outside golden period |
| Post-relist window (L521) | `get_next_golden_hour` | called at L522 | ✗ BROKEN | After 16:10, returns 17:10 — window check always fails |
| Close-to-golden (L557) | `get_next_golden_hour` | called at L558 | ⚠️ PARTIAL | Same issue — can't detect proximity after golden passes |
| `is_in_hold_window` | `is_in_golden_period` | called at L295 | ✓ WIRED | Unchanged |
| Normal relist else | `executor.relist_all/per_listing` | L492-514 | ✓ WIRED | Full relist logic present |

### Root Cause Analysis

**Fixes 2 and 3 share the same root cause:** `get_next_golden_hour(now)` always returns the NEXT future golden target. Once a golden passes (e.g., 16:10:01), it returns the next one (17:10), making any "close to golden" or "in golden window" check fail for the remainder of the hour.

The old broken check (`now_after.minute >= 10 and now_after.minute < 15`) at least worked by checking the minute digit directly. The new seconds-based check is more elegant in concept but uses the wrong reference point.

**Fix 1 has a different issue:** it lacks a guard for `is_in_golden_period()`, so it fires even outside the golden period.

### Correct Approaches

**Fix 1** should add the golden period guard:
```python
if next_golden and now < next_golden and is_in_golden_period(now):
```

**Fix 2** should check the current time directly, not via `get_next_golden_hour`:
```python
hour = now_after.hour
minute = now_after.minute
in_golden_window = hour in (16, 17, 18) and 9 <= minute <= 12
```

**Fix 3** should also check proximity to the CURRENT golden, not the next:
```python
# Check if within 5 min before OR 3 min after any golden
close_to_golden = False
for h in (16, 17, 18):
    golden_time = now_ne.replace(hour=h, minute=10, second=0, microsecond=0)
    secs = (golden_time - now_ne).total_seconds()
    if -180 < secs < 300:  # 3 min after to 5 min before
        close_to_golden = True
        break
```

### Previous Verification Gap — Corrected

The previous VERIFICATION.md claimed the `elif 0 < seconds_until_golden <= 30` branch (L437-440) was dead code. **This was incorrect.** At 16:09:45:
- `seconds_until_pre_nav` = -15 (past pre-nav, first branch skipped)
- `seconds_until_golden` = 15 (elif condition True)
- Branch IS reachable and functional.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `main.py` | 447-453 | Missing guard condition | ⚠️ Warning | Post-nav wait fires outside golden period, causing 2h+ unnecessary waits |
| `main.py` | 524-530 | Wrong reference point | 🛑 Blocker | Rapid polling for stragglers NEVER works — defeats purpose of Fix 2 |
| `main.py` | 557-562 | Wrong reference point | ⚠️ Warning | Close-to-golden polling only works before golden, not after |

### Human Verification Required

| # | Test | Expected | Why human |
|---|------|----------|-----------|
| 1 | Run bot at 14:00 with expired listings | Bot should relist immediately, NOT wait until 16:10 | Cannot verify actual browser behavior programmatically |
| 2 | Run bot, let relist finish at 16:10:15 | Bot should poll again in 15-20s for stragglers | Cannot verify actual browser behavior programmatically |
| 3 | Run bot at 16:12 with no expired | Bot should poll in 15s (still close to golden) | Cannot verify actual browser behavior programmatically |

### Gaps Summary

**3 gaps found, 1 blocker:**

1. **Fix 1 — Missing guard (Warning):** Post-navigation wait at L447-453 fires even outside the golden period. At 14:00, the bot would wait 2+ hours until 16:10 instead of scanning and relisting immediately. Fix: add `and is_in_golden_period(now)` to the condition.

2. **Fix 2 — Window check broken (Blocker):** The seconds-based window check at L524-530 uses `get_next_golden_hour()` which returns the NEXT future golden. After 16:10 passes, it returns 17:10, making the window check (`-60 < secs < 120`) always False. **Rapid polling for stragglers will NEVER trigger** — this is the exact scenario it was designed for. Fix: check current hour/minute directly instead of comparing to next golden.

3. **Fix 3 — Close-to-golden only works before (Warning):** The `close_to_golden` check at L557-562 has the same root cause. It detects proximity BEFORE the golden (e.g., 16:08) but NOT after (e.g., 16:12). Fix: check proximity to the current golden, not the next one.

---

_Verified: 2026-04-07T00:00:00Z_
_Verifier: Claude (gsd-verifier)_

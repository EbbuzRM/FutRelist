---
status: diagnosed
trigger: "Stale scan data causes false 'Processing items remaining' after relist"
created: 2026-04-13T22:07:00
updated: 2026-04-13T22:10:00
---

## Current Focus

hypothesis: Lines 908-917 in main.py check the stale `scan` object (from BEFORE the relist) for PROCESSING items, producing false warnings and unnecessary rapid polling
test: Verify that `scan` variable is not refreshed between the relist and the Processing check
expecting: The scan variable at line 908 is the same object populated at the start of the cycle — it is NEVER re-scanned after relist
next_action: Confirm root cause with evidence and produce diagnosis

## Symptoms

expected: After a successful relist of all expired+processing items, the bot should use a normal wait interval and not report "Processing items remaining"
actual: After relist succeeds (46/46), bot reports "14 item ancora in Processing dopo relist" and sets next_wait=10, triggering unnecessary rapid polling
errors: False warning: "⚠️ 14 item ancora in Processing dopo relist — polling ogni 10s finché non vengono confermati da EA."
reproduction: Have expired+processing items, trigger relist_all, observe stale scan check fires false warning
started: Recurring throughout April 13 production (8 occurrences logged: 13:46, 13:47, 14:47, 14:47, 18:10, 19:11, 20:11, 21:12)

## Eliminated

(none — first hypothesis matches evidence)

## Evidence

- timestamp: 2026-04-13T22:07
  checked: main.py lines 864-919 (relist block)
  found: |
    Lines 908-911 use `scan.listings` to count PROCESSING items after relist.
    `scan` is populated at line ~840 by `detector.scan_listings()` BEFORE the relist decision.
    It is NEVER refreshed after `executor.relist_all()` at line 889.
    Therefore `processing_remaining` always reflects PRE-RELIST state.
  implication: The stale scan is the direct cause of the false warning

- timestamp: 2026-04-13T22:07
  checked: Production log at 21:11:49 (app.log lines 6972-7029)
  found: |
    Scan at 21:11:49: 46 total (32 EXPIRED + 14 PROCESSING in 'active' section, 0 sold)
    Log: "Scansione completata: 46 listing (0 attivi, 46 scaduti, 14 in processing, 0 venduti)"
    Relist: "Re-list All completato per 46 oggetti" → 46 successi, 0 falliti
    False warning: "⚠️ 14 item ancora in Processing dopo relist — polling ogni 15s"
    Next cycle at 21:12:39: 46 active, 0 expired → relist had already worked
  implication: The relist succeeded for ALL 46 items including the 14 Processing ones. The stale scan check is 100% wrong.

- timestamp: 2026-04-13T22:07
  checked: detector.py lines 306-309
  found: |
    `expired_count = sum(1 for l in listings if l.state in (ListingState.EXPIRED, ListingState.PROCESSING))`
    expired_count ALREADY includes PROCESSING items.
  implication: The user's complaint is correct — "46 scaduti, 14 in processing" is misleading because 14 Processing are INSIDE the 46 scaduti, not additional

- timestamp: 2026-04-13T22:07
  checked: ListingScanResult.processing_count property (listing.py lines 58-60)
  found: |
    `processing_count` is a separate property that counts only PROCESSING items.
    But the log message at detector.py line 321-324 prints both `expired_count` and `processing_count` as if separate categories.
  implication: Log message structure is misleading — "46 scaduti, 14 in processing" reads as 46+14=60 when it's 46 total

- timestamp: 2026-04-13T22:07
  checked: Bug frequency across April 13 production logs
  found: |
    8 occurrences of "Processing dopo relist" false warning:
    - 13:46:29 — 24 items (after 43 relisted)
    - 13:47:15 — 2 items
    - 14:47:03 — 5 items
    - 14:47:48 — 3 items
    - 18:10:42 — 10 items (golden hour)
    - 19:11:07 — 12 items
    - 20:11:41 — 1 item
    - 21:12:04 — 14 items
  implication: Bug is systematic — fires EVERY time there are Processing items in the pre-relist scan

- timestamp: 2026-04-13T22:07
  checked: Log message says "15s" but code says `next_wait = 10`
  found: Code at line 917 sets `next_wait = 10`, but production log shows "15s". This suggests code was recently modified (10→15 or 15→10) but the bug pattern is the same regardless of the exact wait value.
  implication: Minor — the exact wait value changed between versions, but the core bug (stale scan → false warning → rapid polling) is identical

## Resolution

root_cause: |
  Lines 908-917 in main.py check the stale `scan` object for PROCESSING items after relist completes.
  The `scan` variable was populated BEFORE `executor.relist_all()` ran, so it ALWAYS reflects pre-relist state.
  When any PROCESSING items existed before relist, the check finds them and triggers:
  1. False warning: "⚠️ N item ancora in Processing dopo relist"
  2. Rapid polling: next_wait=10 (was 15) instead of normal wait
  3. Wasted cycles: re-scan confirms all items are active, relist had already worked

  Secondary issue: Log message "46 scaduti, 14 in processing" is misleading because
  expired_count (46) already includes PROCESSING items (14 are a subset of the 46).

fix: (pending — goal is find_root_cause_only)
verification: (pending)
files_changed: []

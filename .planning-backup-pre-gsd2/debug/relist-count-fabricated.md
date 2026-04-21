---
status: awaiting_human_verify
trigger: "Il bot riporta 32 successi, 0 falliti ma solo 30 oggetti sono stati relistati sulla Web App. 2 oggetti scaduti NON sono stati relistati."
created: 2026-04-15T21:30:00
updated: 2026-04-15T21:45:00
---

## Current Focus

hypothesis: CONFIRMED — relist_all() fabricated RelistResult objects with success=True for ALL items without verifying actual relist outcome
test: Fixed both relist.py (removed fictitious results) and main.py (added post-relist verification scan)
expecting: After fix, succeeded = pre_expired - post_expired, failed = post_expired (verified by scan)
next_action: Wait for human verification

## Symptoms

expected: Bot should report accurate succeeded/failed counts based on actual relist results verified by a second scan
actual: Bot reports "32 successi, 0 falliti" when only 30 items were actually relisted — 2 expired items were not relisted but counted as successes
errors: No error messages; the bug is silent — failed items are reported as successes
reproduction: Have items on Transfer List where some cannot be relisted (e.g., price below minimum); run bot in relist_mode="all"; observe that all items are reported as succeeded regardless of actual outcome
started: Always been this way — relist_all() was designed this way from the start

## Eliminated

## Evidence

- timestamp: 2026-04-15T21:30:00
  checked: browser/relist.py relist_all() lines 94-161
  found: Lines 124-129 create fictitious RelistResult objects: `[RelistResult(listing_index=-1, player_name=f"ITEM {i+1}", old_price=None, new_price=None, success=True) for i in range(count)]`. ALL items are hardcoded as success=True regardless of actual outcome.
  implication: The succeeded count is always equal to the count parameter passed in, and failed is always 0.

- timestamp: 2026-04-15T21:30:00
  checked: browser/relist.py _check_relist_errors() lines 163-183
  found: Only checks for DOM-level error banners. Does NOT scan for remaining expired items. Only detects catastrophic failures (error messages in the page), not individual item failures.
  implication: If 2 out of 32 items fail silently (e.g., price below min, item not relistable), _check_relist_errors() won't catch them.

- timestamp: 2026-04-15T21:30:00
  checked: main.py lines 1023-1026
  found: After relist_all(), code blindly uses batch.succeeded and batch.total - batch.succeeded for succeeded/failed. No post-relist verification scan.
  implication: The main loop propagates the fabricated counts to logging, notifications, and bot_state.

- timestamp: 2026-04-15T21:30:00
  checked: main.py _golden_retry_relist() lines 485-594
  found: The golden retry DOES do a fresh scan (line 557: `scan = detector.scan_listings()`) and relists remaining expired items. This is the correct pattern but it only runs during golden windows.
  implication: The verification pattern exists in the codebase already. We need to apply the same pattern (fresh scan after relist) to the initial relist_all() path.

- timestamp: 2026-04-15T21:30:00
  checked: main.py notification accumulator lines 1106-1137
  found: notification_accumulator["relisted"] += succeeded uses the fabricated count. _send_batch_notification() at line 358-404 uses accumulator["relisted"] directly.
  implication: Telegram notifications report inflated success counts.

## Resolution

root_cause: relist_all() in browser/relist.py fabricated RelistResult objects with success=True for ALL count items without verifying the actual relist outcome. No post-relist scan existed to confirm how many items were actually relisted vs. how many remain expired. The _check_relist_errors() method only catches catastrophic DOM-level error banners, not individual item-level failures (e.g., items that couldn't be relisted due to price constraints).
fix: 1) Removed fictitious RelistResult list from relist_all() — now returns an empty batch result as placeholder. 2) Added post-relist verification scan in main.py after relist_all() — scans the Transfer List to count actual remaining expired items, then computes succeeded = (pre_expired - post_expired) and failed = post_expired. 3) Applied same fix to _golden_retry_relist() which also used batch.succeeded from the fabricated results.
verification: 648 existing tests pass (8 pre-existing failures in test_golden_retry.py unrelated to changes). Manual verification pending.
files_changed: [browser/relist.py, main.py]

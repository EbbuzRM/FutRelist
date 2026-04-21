---
status: awaiting_human_verify
trigger: "Conteggio falliti errato dopo relist — Processing items non ancora completati"
created: 2026-04-16T01:30:00
updated: 2026-04-16T01:50:00
---

## Current Focus

hypothesis: CONFIRMED — Post-relist verification counts ALL remaining expired as "failed", including Processing items
test: Fixed both locations, all 658 tests pass
expecting: User confirms the fix works in real usage
next_action: Wait for human verification

## Symptoms

expected: Items in PROCESSING state should not be counted as "failed" after relist
actual: After "Re-list All", verification scan counts remaining expired (including Processing) as "failed"
errors: Log shows "11 falliti" when those 11 are Processing items that succeed in the next cycle
reproduction: Have items in Processing state when bot clicks "Re-list All"
started: Always present when Processing items exist during relist

## Eliminated

(none)

## Evidence

- timestamp: 2026-04-16T01:30:00
  checked: main.py lines 1042-1049 (post-relist verification for relist_mode="all")
  found: `failed = post_expired` counts ALL remaining expired as failures
  implication: PROCESSING items wrongly counted as failed

- timestamp: 2026-04-16T01:30:00
  checked: detector.py lines 306-309
  found: `expired_count` includes both EXPIRED and PROCESSING states
  implication: Pre/post expired counts mix truly expired and processing items

- timestamp: 2026-04-16T01:30:00
  checked: main.py lines 577-580 (_golden_retry_relist)
  found: Same bug: `failed = post_scan.expired_count`
  implication: Golden retry also counts Processing as failed

- timestamp: 2026-04-16T01:30:00
  checked: ListingScanResult.processing_count property
  found: Already exists and counts PROCESSING items
  implication: Can use it to separate truly failed from still-processing

## Resolution

root_cause: Post-relist verification uses `failed = post_expired` which includes items in PROCESSING state. The `expired_count` from ListingScanResult includes both EXPIRED and PROCESSING items, so all remaining "expired" items were counted as failures regardless of whether they were genuinely failed (EXPIRED) or just pending (PROCESSING).
fix: Two changes in main.py:
1. Main loop post-relist verification (lines ~1045-1075): Calculate `pre_processing` before wait, extend wait to 5000ms if Processing items exist, use `truly_failed = max(post_expired - post_processing, 0)` to count only genuinely failed items. Improved verification log message to show Processing vs truly-failed breakdown.
2. Golden retry post-relist verification (lines ~575-583): Same fix — `truly_failed = max(post_scan.expired_count - post_processing, 0)` instead of `failed = post_scan.expired_count`. Also extended wait from 2000ms to 3000ms.
3. Updated test_golden_retry.py: Fixed pre-existing test failures by adding `processing_count` parameter to bypass early-return, and adjusted scan side_effects for the additional post-relist verification scans.
verification: All 658 tests pass. Python syntax verified.
files_changed: [main.py, tests/test_golden_retry.py]

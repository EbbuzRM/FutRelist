---
phase: fix-stale-processing-check
plan: 01
subsystem: main-loop, detector
tags: [bugfix, stale-data, log-clarity]
key-files:
  created: []
  modified: [main.py, browser/detector.py]
decisions:
  - Removed stale scan Processing check after relist — next scan cycle handles genuine Processing items naturally
  - Used Italian "di cui" (of which) format to clarify Processing items are a subset of expired
metrics:
  duration: 2m
  completed: 2026-04-13
---

# Phase fix-stale-processing-check Plan 01: Fix Stale Processing Check Summary

Removed false-positive rapid polling after relist and fixed misleading scan log that implied Processing items were additional to expired count.

## Changes Made

### Task 1: Remove stale Processing check after relist in main.py
- **File:** `main.py`
- **Change:** Replaced 14-line stale `scan.listings` PROCESSING check (lines 905-919) with single `_compute_next_wait()` call
- **Root cause:** `scan` object is populated BEFORE relist, so counting PROCESSING items from it after relist always reported false positives — 8 occurrences on Apr 13, all false
- **Impact:** After successful relist, bot now uses normal wait interval instead of 10s rapid polling based on stale data
- **Commit:** d63d342

### Task 2: Fix misleading scan log in detector.py
- **File:** `browser/detector.py`
- **Change:** `", {processing_count} in processing"` → `" (di cui {processing_count} in processing)"`
- **Root cause:** Log printed expired and processing as separate counts, implying 46+14=60 total when there were only 46 items
- **Impact:** Scan log now reads "46 scaduti (di cui 14 in processing)" making clear Processing is a subset of expired
- **Commit:** d63d342

## Verification

| Check | Result |
|-------|--------|
| main.py syntax | OK |
| detector.py syntax | OK |
| Import check | OK |
| `processing_remaining` in main.py | 0 occurrences |
| `di cui` in detector.py | 1 occurrence |
| pytest (648 tests) | ALL PASSED |
| Golden hour logic | Untouched |
| Relist `else` fallback | Preserved |

## Deviations from Plan

None - plan executed exactly as written.

Note: The commit includes pre-existing uncommitted changes from prior phases (golden hour window fix, interruptible waits, etc.) that were in main.py's working tree. The task-specific changes are limited to: (1) stale Processing check removal and (2) detector.py log format fix.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or security surface introduced.

## Self-Check: PASSED

- main.py: parses OK
- browser/detector.py: parses OK
- Commit d63d342: FOUND

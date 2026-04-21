---
phase: fix-stale-processing-check
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [main.py, browser/detector.py]
autonomous: true
requirements: [BUG-stale-scan, BUG-misleading-log]
must_haves:
  truths:
    - "After successful relist, bot uses normal wait interval (no false rapid polling)"
    - "No false 'Processing items remaining' warning after relist"
    - "Log message makes clear that processing items are a subset of expired, not additional"
  artifacts:
    - path: "main.py"
      provides: "Removed stale scan Processing check after relist"
      contains: "_compute_next_wait"
    - path: "browser/detector.py"
      provides: "Fixed scan result log message"
      contains: "di cui"
  key_links:
    - from: "main.py relist block"
      to: "_compute_next_wait"
      via: "direct call after relist"
      pattern: "_compute_next_wait"
---

<objective>
Fix two bugs caused by stale scan data and misleading log formatting.

Purpose: The bot fires a false "N item ancora in Processing dopo relist" warning after every relist that had Processing items, triggering unnecessary 10s rapid polling. Additionally, the scan log "46 scaduti, 14 in processing" reads as 60 items when there are only 46.

Output: Clean relist flow with normal wait intervals and clear log messages.
</objective>

<context>
@.planning/debug/stale-processing-check.md

Root cause (confirmed by debugger):
1. main.py lines 908-917: After `relist_all()` succeeds, code checks the STALE `scan` object (populated BEFORE relist) for PROCESSING items. Always reports them as remaining → false warning + rapid polling.
2. detector.py lines 321-324: Log prints `expired_count` and `processing_count` as separate categories, but `expired_count` already INCLUDES Processing items.

Critical AGENTS.md rules:
- Do NOT modify golden hour logic
- Every relist block MUST have an `else` fallback for normal relist
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove stale Processing check after relist in main.py</name>
  <files>main.py</files>
  <action>
Replace lines 905-919 in main.py. The current code has a stale scan check:

```python
# Safety net: se ci sono ancora item Processing dopo il relist,
# probabilmente EA non li ha ancora spostati in Expired.
# Polling aggressivo a 10s finché non spariscono.
processing_remaining = sum(
    1 for l in scan.listings
    if l.state == ListingState.PROCESSING
)
if processing_remaining > 0:
    fifa_logger.info(
        f"⚠️ {processing_remaining} item ancora in Processing dopo relist "
        f"— polling ogni 10s finché non vengono confermati da EA."
    )
    next_wait = 10
else:
    next_wait = _compute_next_wait(scan, datetime.now(), fifa_logger)
```

Replace the ENTIRE block (lines 905-919) with a single line:

```python
                    next_wait = _compute_next_wait(scan, datetime.now(), fifa_logger)
```

Rationale: `scan` is stale (populated before relist), so counting PROCESSING items from it is always wrong. If Processing items genuinely remain after relist, the next scan cycle will detect them naturally and handle them correctly. The 10s rapid polling was a safety net based on bad data — it only ever fired false positives (8 occurrences on Apr 13, all false).

IMPORTANT: This change is inside the `else` block at line 882 (the normal relist path). The structure `if in_hold ... else ... relist ... next_wait` must remain intact. Only the sub-block (lines 905-919) is being simplified. The outer `else` at line 882 and its closing must be preserved.
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('main.py').read()); print('syntax OK')"</automated>
  </verify>
  <done>
    - Lines 905-919 replaced with single `_compute_next_wait` call
    - No stale `scan.listings` Processing check after relist
    - No `processing_remaining` variable after relist
    - `next_wait = 10` rapid polling removed from this location
    - File parses without syntax errors
    - The relist `else` block structure preserved (golden hour logic untouched)
  </done>
</task>

<task type="auto">
  <name>Task 2: Fix misleading scan log in detector.py</name>
  <files>browser/detector.py</files>
  <action>
Change the log message at lines 321-324 in browser/detector.py.

Current (misleading — reads like 46+14=60 items):
```python
processing_log = f", {processing_count} in processing" if processing_count > 0 else ""
logger.info(
    f"Scansione completata: {result.total_count} listing "
    f"({active_count} attivi, {expired_count} scaduti{processing_log}, {sold_count} venduti)"
)
```

Replace with (clear that processing is a subset of expired):
```python
processing_log = f" (di cui {processing_count} in processing)" if processing_count > 0 else ""
logger.info(
    f"Scansione completata: {result.total_count} listing "
    f"({active_count} attivi, {expired_count} scaduti{processing_log}, {sold_count} venduti)"
)
```

Change summary:
- `", {processing_count} in processing"` → `" (di cui {processing_count} in processing)"`
- Result: "46 scaduti (di cui 14 in processing)" instead of "46 scaduti, 14 in processing"
- The parenthetical "di cui" (of which) makes it clear that the 14 Processing are a subset of the 46 expired, not additional items
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('browser/detector.py').read()); print('syntax OK')"</automated>
  </verify>
  <done>
    - Log message uses "di cui X in processing" format (subset clarity)
    - No separate count that implies addition
    - File parses without syntax errors
  </done>
</task>

</tasks>

<verification>
1. `python -c "import ast; ast.parse(open('main.py').read()); print('OK')"` — syntax check
2. `python -c "import ast; ast.parse(open('browser/detector.py').read()); print('OK')"` — syntax check
3. `python -c "from main import *; print('import OK')"` — import check (if feasible)
4. `pytest tests/ -x` — existing test suite passes
5. Grep for `processing_remaining` in main.py — should return 0 matches
6. Grep for `di cui` in detector.py — should return 1 match
</verification>

<success_criteria>
- No stale scan Processing check after relist in main.py
- After relist, `_compute_next_wait` is called directly (no 10s rapid polling branch)
- Scan log message uses "di cui" to clarify processing items are subset of expired
- All existing tests pass
- Golden hour logic untouched
- Relist `else` fallback preserved
</success_criteria>

<output>
After completion, create `.planning/quick/fix-stale-processing-check/01-SUMMARY.md`
</output>

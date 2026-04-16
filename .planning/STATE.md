---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: Two-Phase Post-Relist Verification
status: production
last_updated: "2026-04-16T12:00:00Z"
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 24
  completed_plans: 24
---

# Project State

## Status: PRODUCTION / MAINTENANCE MODE

All planned phases complete. The bot is running in production, relisting items successfully.

### Today's Fixes (April 16, 2026)

**Bug Fix 4: Two-Phase Post-Relist Verification with Auto-Relist**
- After "Re-list All", the bot did a single verification scan. If Processing items hadn't completed yet on EA's side, they were counted as "failed"
- Fix: two-phase verification:
  1. **1st round**: Re-list All → wait 5s → scan → count `first_succeeded` and `truly_expired` (expired NOT in Processing)
  2. **2nd round (conditional)**: If `truly_expired > 0` after 1st round → Re-list All immediately → wait 3s → final scan → total count (1st + 2nd round)
- If 2nd relist fails → log warning, use only 1st round counts
- Processing items are NEVER counted as failed — next cycle will pick them up
- Same fix applied both in main loop and `_golden_retry_relist()`
- Improved logs: `[Verifica 1°]`, `[Verifica 2°]` to distinguish rounds

### Previous Fixes (April 14, 2026)

**Bug Fix: Stale Processing Check (commit d63d342)**
- After `relist_all()`, the code checked the STALE `scan` object for PROCESSING items, causing false "⚠️ 14 item ancora in Processing dopo relist" warnings and unnecessary 10-15s rapid polling.
- Fix: Removed the stale scan check entirely. After relist, compute next_wait normally. The next cycle will verify naturally.
- Also fixed: Misleading log message "46 scaduti, 14 in processing" → "46 scaduti (di cui 14 in processing)" to make clear Processing is a subset of expired, not additional.
- Also cleaned up: Removed sync-conflict files and unnecessary scroll code.

**Feature: Golden Processing Retry Loop (commits b9fc754 + 1f60c59)**
- New function: `_golden_retry_relist()` in main.py
- During golden window (:09-:11), after initial relist succeeds, if Processing items remain: wait 5-10s random (interruptible by Telegram) → navigate to Transfer List → fresh scan (NEVER stale data) → relist if expired_count > 0, accumulate stats → repeat until clear or golden window closes.
- Only during golden hours — outside golden window, normal cycle handles it.
- 10 new unit tests in tests/test_golden_retry.py covering: no retry outside golden, single retry, multiple retries, window closes mid-retry, reboot during wait, navigation failure, per_listing mode, session recovery, wait timing, fresh scan verification.

### Tonight's Fixes (April 13, 2026)

**Bug Fix: Golden Hour "Missed Target" due to millisecond delay**
- At 16:10:01 the bot calculated the next golden as 17:10 instead of acting on 16:10, causing an unnecessary 1h HOLD.
- Fixed: `get_next_golden_hour()` now considers a golden target still "current" as long as the time is within the `GOLDEN_RELIST_WINDOW` (:09-:11).
- Updated: `tests/test_golden_timeline.py` now includes 7 new test cases for boundary conditions (16:10:00, 16:11:59, etc.) to ensure the fix is verified and permanent.

**Stability & Logic Improvements**
- **Manual Relist Heuristic**: Improved detection to look for timers near 1h/3h/6h, reducing false positives.
- **Preventive Session Check**: Added an "aggressive" session check 3 minutes before any Golden Hour target to ensure the bot is logged in for the pre-nav.
- **Telegram Responsiveness**: Modified `wait_interruptible` and heartbeat loops to break immediately when a Telegram command is queued, making the bot much more responsive to user interaction.
- **Startup Blindness Fix**: The bot now always performs a full scan on the first cycle (Cycle 1) even during a Golden HOLD window. This ensures it captures the "ground truth" of the Transfer List (and detects manual relists) before entering efficient heartbeat-based HOLD.
- **Precision Wait Guard**: Added `is_close_to_golden` guard to the precision wait logic. This prevents the bot from entering long blocking sleeps (e.g., 48 minutes at 17:21) before scanning the Transfer List.
- **Async Precision Wait**: Replaced `time.sleep` with `wait_interruptible` in the precision wait block, ensuring the bot remains responsive to Telegram commands even during the final countdown to a Golden Hour.
- **Processing Timer Optimization**: Reduced aggressive polling interval from 15s to 10s for items in `PROCESSING` state or near expiry, ensuring faster relisting during critical windows.
- **Perfect Pre-Nav Sync**: Optimized the pre-nav loop to hit exactly `:09:30` by disabling heartbeats in the final 3 minutes and performing a guaranteed session check.

### Shipped Milestones
- v1.0 Auto-Relist MVP — SHIPPED 2026-03-23
- v1.1 Telegram Commands & Sold Cleanup — SHIPPED 2026-04-06
- v1.2 Protection & Stealth (Console Mode, Heartbeat, Reboot, Batch Notifications) — SHIPPED 2026-04-11
- v1.3 Golden Hour Bug Fixes (3 critical fixes + 519 timeline tests) — SHIPPED 2026-04-12
- v1.4 Wait All Expired & Telegram Reports — SHIPPED 2026-04-13
- v1.5 PROCESSING State Fix — SHIPPED 2026-04-13
- v1.6 Batch Report & Screenshot Fix — SHIPPED 2026-04-13
- v1.7 Golden Processing Retry — SHIPPED 2026-04-14
- v1.8 Two-Phase Post-Relist Verification — SHIPPED 2026-04-16

### All Phases Complete (7/7)

- [x] Phase 1: Browser Setup & Authentication (BROWSER-01, BROWSER-02, BROWSER-03)
- [x] Phase 2: Transfer Market Navigation (BROWSER-04, DETECT-01~04)
- [x] Phase 3: Auto-Relist Core (RELIST-01~04)
- [x] Phase 4: Configuration System (CONFIG-01~04)
- [x] Phase 5: Logging & Error Handling (LOG-01~04, ERROR-01~04)
- [x] Phase 6: Telegram Bot Commands + Sold Items Cleanup (TELEGRAM-01~10)
- [x] Phase 7: Bug Fixes & Stability (GOLDEN-FIX-01~03, POLLING-01)

### Test Suite: 658 tests, all passing
- 132 original unit/feature tests
- 526 golden timeline simulation tests (tests/test_golden_timeline.py)
- 10 golden processing retry tests (tests/test_golden_retry.py)

### Production Verification
- 53 items relisted, 0 failures
- 61 expired items recovered after hold window fix
- EA popup dismissal working with 3-attempt retry
- Golden hour relist firing correctly at :10 with :09-:11 window
- Relist batch notifications showing accurate count of active/expired items
- Handling of "Processing" elements effectively waits before relist
- Aggregated Telegram reports show consistent item counts (capped at total_count)
- Golden Processing Retry: during golden window, automatically retries relist for Processing items with fresh scans

### Tonight's Fixes (April 12, 2026)

**Bug 1 (commit 20da86e): Golden Hour wait skips when already in window**
- At 16:10 the bot waited 59 min until 17:10 instead of relisting immediately
- Fixed: Added `is_in_golden_window(now)` check — if already in :09-:11 window, skip the sleep and relist right away

**Bug 2 (commit aa52cb3): EA popup blocks Transfer List click**
- `view-modal-container form-modal` intercepted pointer events for 30s causing timeout cascade
- Fixed: Added `dismiss_popups()` + Escape between Transfers click and Transfer List click, plus 3-attempt retry loop

**Bug 3 (commit 20da86e): Hold window too aggressive after last golden**
- 61 expired items not relisted at 18:14 — hold window kept items waiting for a 19:10 golden that doesn't exist
- Fixed: When `get_next_golden_hour() is None` (no more goldens today), override hold and relist immediately

**Polling tweak (commit fe2c2ea): Golden ritardatari polling → 10s fixed**
- Changed from 15-20s random interval to 10s fixed for more responsive ritardatari catch during golden windows

### Current Activity
[2026-04-16T12:00:00Z] v1.8 Two-Phase Post-Relist Verification: After "Re-list All", single verification scan miscounted Processing items as failures. Fix: two-phase verification — 1st round (relist → 5s → scan → separate truly expired from Processing), 2nd conditional round (if truly_expired > 0 → immediate re-relist → 3s → final scan). Processing items never counted as failed. Applied in both main loop and _golden_retry_relist(). Logs now show [Verifica 1°] / [Verifica 2°].

[2026-04-14T16:30:00Z] v1.7 Golden Processing Retry: Fixed stale Processing check that caused false warnings and unnecessary rapid polling after relist_all(). Added _golden_retry_relist() function that, during golden window, automatically retries relist for items still in Processing state using fresh scans (never stale data). Includes 10 new unit tests. Total test count: 658.

[2026-04-13T14:45:00Z] v1.6 Batch Report & Screenshot Fix: Corrected inconsistent numbers in aggregated Telegram notifications (49 active + 55 relisted on 51 total items). Now "Relistati" is capped at total_count and reflect batch progress, while "Totale oggetti" gives the overall context.

[2026-04-13T11:30:00Z] PROCESSING state fix shipped. New ListingState.PROCESSING enum captures items in EA limbo (expired but still visible as "active" in DOM). Fixes in detector.py: added "processing"/"elaborazion" detection → returns PROCESSING instead of UNKNOWN. Main.py safety net: after relist, if PROCESSING items remain, force 15s wait instead of normal expiry wait. Notification accumulator now tracks expired_detected across all cycles in batch.

[2026-04-13T11:00:00Z] v1.4 Wait All Expired & Telegram Reports shipped. Added the "wait for all active/processing to expire" logic to keep relist queue intact outside golden hours, and updated the telegram report to strictly count active listings with a timer.
[2026-04-12T23:30:00Z] v1.3 Golden Hour Bug Fixes shipped. 3 critical bugs fixed, 519 timeline tests added. All 7 phases complete. Project in production/maintenance mode.
[2026-04-12T10:42:00Z] Batch Telegram notifications: bot now accumulates relist events expiring within 120s and sends ONE notification with total count instead of 2-3 separate messages.
[2026-04-11T17:01:00Z] Milestone v1.2 (Protection & Stealth) shipped: Console Mode, Heartbeat, Reboot, Batch Notifications
[2026-04-06T14:12:00Z] Milestone v1.1 (Telegram Commands) shipped: 8 Telegram commands, SoldHandler, BotState
[2026-03-23T07:39:00Z] Milestone v1.0 (Auto-Relist MVP) shipped: Full auto-relist with golden hours, pricing, logging, error recovery

### Accumulated Context (from all milestones):
- Python 3.13 + Playwright + python-dotenv + rich + tenacity
- Browser controller with persistent profile (no 2FA repeats)
- AuthManager: 2-step EA login (email→NEXT→password→Sign in), session persistence
- Navigator: page object pattern, popup dismissal, retry loops
- Detector: bulk DOM extraction via eval_on_selector_all, Italian/English keyword mapping
- RelistExecutor: configurable price adjustment (percentage/fixed), FIFA bounds (200-15M)
- ConfigManager: typed dataclasses, deep-merge migration, CLI subcommands
- Golden Hour logic: 16:10/17:10/18:10 with :09-:11 window, pre-nav at :09:30, hold otherwise
- Rate limiting: 2-5s random delays (anti-detection), 10s ritardatari polling
- Error handling: session recovery, retry with exponential backoff, EA modal dismissal
- Telegram: 8 commands (/status, /pause, /resume, /force_relist, /screenshot, /del_sold, /logs, /help)
- BotState: thread-safe with threading.Lock, force_relist flag, pause/resume, reboot event
- Console Mode: Deep Sleep via /console and /online commands
- Heartbeat: dynamic click 'Clear Sold' every 2.5-5 min random
- Aggregated reports: capped counts at total_count for logical consistency
- Golden Processing Retry: _golden_retry_relist() retries Processing items during golden window with fresh scans, interruptible by Telegram
- Two-Phase Post-Relist Verification: 1st round scans after relist, 2nd conditional round re-relists truly expired items; Processing never counted as failed
- 519 timeline simulation tests covering every minute 14:00-20:59 + golden boundaries
- Every relist block MUST have an `else` fallback for normal relist (AGENTS.md rule)

Last updated: 2026-04-16T12:00:00Z

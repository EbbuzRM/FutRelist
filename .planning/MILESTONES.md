## Shipped Milestones

### v1.0 Auto-Relist MVP — SHIPPED 2026-03-23
**Phases completed:** 5 phases (1-5), 16 plans
**Tests:** 68 passing
**Key accomplishments:**
- Playwright browser automation with persistent profile (no repeated 2FA)
- EA login flow (email → password → session cookies)
- Transfer Market navigation with popup dismissal
- DOM-based listing detection (active/expired/sold)
- Auto-relist with configurable price adjustment (percentage or fixed, FIFA bounds 200-15M)
- RelistExecutor with dialog handling
- ConfigManager with typed dataclasses, CLI subcommands, deep-merge migration
- Structured JSONL logging + rich console output
- Rate limiting (2-5s random delays), error recovery, session persistence
- Golden Hour scheduling: 17:10/18:10 with HOLD period from 16:10 and pre-nav at :09:00

---

### v1.1 Telegram Commands & Sold Cleanup — SHIPPED 2026-04-06
**Phase completed:** Phase 6, 2 plans
**Tests:** 112 passing
**Key accomplishments:**
- BotState: thread-safe dataclass with threading.Lock (pause/resume/force_relist/reboot flags)
- TelegramHandler: 8 command handlers (/status, /pause, /resume, /force_relist, /screenshot, /del_sold, /logs, /help)
- SoldHandler: automated sold items navigation, credit collection, cleanup
- Thread-safe communication between Telegram thread and main loop
- Chat authentication (only authorized chat_id receives commands)
- Long polling with graceful shutdown

---

### v1.2 Protection & Stealth — SHIPPED 2026-04-11
**Tests:** 122 passing
**Key accomplishments:**
- Console Mode: Deep Sleep via Telegram /console and /online commands
- Heartbeat: dynamic click 'Clear Sold' every 2.5-5 min random to appear human
- Automatic detection of manual relist during Golden Hours
- Automatic handling of EA 'Cannot Authenticate' modal
- Reboot command: /reboot triggers clean shutdown + subprocess respawn via threading.Event
- Batch Telegram notifications: accumulates relist events within 120s, sends single summary
- Golden Hold Loop updated with reactive heartbeat

---

### v1.3 Golden Hour Bug Fixes — SHIPPED 2026-04-12
**Tests:** 641 passing (122 original + 519 golden timeline)
**Key accomplishments:**
- **Fix 1 (20da86e):** Golden hour wait logic — added `is_in_golden_window(now)` to skip sleep when already in :09-:11 window. Previously waited 59 min from 16:10 to 17:10.
- **Fix 2 (aa52cb3):** EA popup blocking — added `dismiss_popups()` + Escape between Transfers click and Transfer List click, plus 3-attempt retry loop. EA's `view-modal-container form-modal` was intercepting pointer events.
- **Fix 3 (20da86e):** Hold window override — when `get_next_golden_hour() is None` (no more goldens today), override hold and relist immediately. 61 expired items were stuck at 18:14 waiting for non-existent 19:10 golden.
- **Polling tweak (fe2c2ea):** Ritardatari polling from 15-20s random → 10s fixed for faster catch during golden windows.
- **519 timeline simulation tests:** Covering every minute from 14:00-20:59 and all golden hour boundary conditions.
- **Production verified:** 53 items relisted, 0 failures.

---

### v1.7 Golden Processing Retry — SHIPPED 2026-04-14
**Tests:** 658 passing (132 original + 519 golden timeline + 10 golden retry + 7 misc)
**Key accomplishments:**
- **Bug Fix (d63d342):** Removed stale Processing check after relist_all(). The STALE `scan` object was checked for PROCESSING items, causing false "⚠️ 14 item ancora in Processing dopo relist" warnings and unnecessary 10-15s rapid polling. After relist, next_wait is computed normally and the next cycle verifies naturally.
- **Log clarity (d63d342):** Fixed misleading log "46 scaduti, 14 in processing" → "46 scaduti (di cui 14 in processing)" — Processing is a subset of expired, not additional items.
- **Cleanup (d63d342):** Removed sync-conflict files and unnecessary scroll code.
- **Feature (b9fc754 + 1f60c59):** Added `_golden_retry_relist()` function in main.py. During golden window (:09-:11), after initial relist succeeds, if Processing items remain: wait 5-10s random (interruptible by Telegram) → navigate to Transfer List → fresh scan (NEVER stale data) → relist if expired_count > 0, accumulate stats → repeat until clear or golden window closes. Only active during golden hours — outside golden window, normal cycle handles it.
- **10 new unit tests** in tests/test_golden_retry.py covering: no retry outside golden, single retry, multiple retries, window closes mid-retry, reboot during wait, navigation failure, per_listing mode, session recovery, wait timing, fresh scan verification.

---

### v1.8 Two-Phase Post-Relist Verification — SHIPPED 2026-04-16
**Tests:** 658 passing (132 original + 519 golden timeline + 10 golden retry + 7 misc)
**Key accomplishments:**
- **Bug Fix 4: Two-Phase Post-Relist Verification with Auto-Relist.** After "Re-list All", the bot performed a single verification scan. Processing items not yet completed by EA were incorrectly counted as "failed".
- **1st round**: Re-list All → wait 5s → scan → count `first_succeeded` and `truly_expired` (expired items NOT in Processing state)
- **2nd round (conditional)**: If `truly_expired > 0` after 1st round → Re-list All immediately → wait 3s → final scan → total count (1st + 2nd round combined)
- If 2nd relist fails → log warning, fall back to 1st round counts only
- Processing items are NEVER counted as failed — the next cycle will pick them up naturally
- Same fix applied both in the main loop and `_golden_retry_relist()`
- Improved log labels: `[Verifica 1°]`, `[Verifica 2°]` to clearly distinguish verification rounds

---

### v1.9 Metrics & Reboot Stability — SHIPPED 2026-04-20
**Tests:** 674 passing (148 original + 526 golden timeline)
**Key accomplishments:**
- **RebootRequestError:** Implemented a dedicated exception for asynchronous reboot requests. Prevents the bot from crashing during sensitive operations (like Golden Loop) by triggering a graceful loop break instead of a fatal process exit.
- **Metric Decoupling:** Refactored `BotState` to separate "Last Cycle" statistics from "Historical Totals". Cycle counters are now reset precisely at the start of each new browser scan cycle.
- **Telegram Status Upgrade:** The `/status` command now displays dual counters: results of the most recent relist action and the cumulative success/fail count for the entire session.
- **Console Session Robustness:** Optimized `ConsoleSessionError` handling to perform a clean browser shutdown and silent restart, reducing "false alarm" critical notifications for the user.
- **Test Suite Expansion:** Added 16 new tests verifying the thread-safety and logic of the new metric tracking and exception flow.

---

### v1.10 Golden Stability & Session Heartbeat — SHIPPED 2026-04-21
**Tests:** 674 passing
**Key accomplishments:**
- **Golden Hour Pre-Nav Fix:** Separated the pre-navigation wait into two distinct phases. The bot now waits at :08:00 until exactly :09:00 before navigating. This prevents the bot from "parking" too early on the Transfer List and ensures perfect timing for the :10:00 relist.
- **Human-like HOLD Logic:** Removed the 60-second hard cap on the wait timer during HOLD periods. The bot now sleeps for extended periods (e.g., ~40-50 minutes) instead of scanning every minute, drastically reducing bot-like behavior.
- **Heartbeat Timeout Fix:** Resolved recurring 3000ms timeout errors when clicking "Transfers" for session maintenance. Added an `Escape` key press to clear invisible EA overlays and implemented `force=True` on the click action.
- **AGENTS.md Protection:** Formalized the Golden Hour timing rules in documentation to prevent future logic regressions by other agents.

---

### v1.11 Code Quality & Timing Precision — SHIPPED 2026-05-06
**Tests:** 686 passing (155 unit + 531 golden timeline)
**Key accomplishments:**
- **Code Review Fixes (CR-02, HI-01):** Fixed `_golden_retry_loop` return values (3 not 4); fixed logger warning format `%s` → `{var}` in config.py and rate_limiter.py
- **Maintainability (ME-01/02/03):** Fixed `sys` import order in log_config.py; replaced `list.pop(0)` with `deque.popleft()` in BotState pending commands (O(1)); moved AuthManager imports to module level in relist.py
- **Dependency Injection (LO-01):** Centralized RateLimiter via dependency injection across navigator, relist, sold_handler
- **Root Cause Fix: `get_next_golden_hour()`:** Modified to return the **next future** golden hour instead of the current one when inside the :09-:11 window. All callers now correctly wait for future GH.
- **Deadline Precision:** Simplified `_compute_deadline()` removing defensive logic; added deadline check in `wait_with_heartbeat()` to prevent oversleep past :08:00 with 1s safety margin and immediate exit when deadline reached.
- **Click-Shield Fix:** Implemented `wait_for_click_shield()` with `wait_for_function()` (Playwright best practice) in browser/auth.py
- **Error Screenshots:** Added `send_telegram_error_with_screenshot()` in notifier.py for visual diagnostics of critical errors
- **Test Suite Expansion:** Added `test_relist_engine.py`, `test_relist_imports.py` and updated existing test files

---

### v1.12 Stale Page Detection & Processing Improvements — SHIPPED 2026-05-11
**Tests:** 693 passing
**Key accomplishments:**
- **Root Cause Fix: Telegram Relist Overcount:** EA leaves items briefly in `section='active'` with `state='Expired'` after relist. Fixed detector.py to classify `Expired`/`Scaduto` text inside active section as `ListingState.EXPIRED`. Resolved "17 rilistati" bug (was counting 16 real + 1 phantom).
- **Root Cause Fix: Processing Limbo & Double Notifications:** `_processing_wait_loop` now executes relist **immediately** after detecting Processing→Expired transition in the same cycle. Processing items outside golden window now get 15 attempts (was 3) with 30-60s waits and 300s total timeout. Fixed stale `_last_scan_result` causing processing wait bypass.
- **Stale Page Detection:** Added detector in `process_cycle`: if bot does ≥10 rapid cycles (wait ≤30s) consecutively without finding expired items, forces `page.reload()` to get fresh data from EA server. Prevents infinite polling loop on frozen JavaScript timers after session expiry.
- **Heartbeat Auto-Recovery:** `_execute_heartbeat()` now calls `ensure_session()` on session expiry detection. If recovery fails, sends Telegram notification with screenshot and raises `RebootRequestError`.
- **Reboot with os.execv():** `handle_reboot()` now uses `os.execv(sys.executable, [sys.executable, "main.py"])` to fully replace the process. All Python modules are reloaded from disk. Previously `while True` in main.py restarted in the same interpreter with stale modules.
- **Processing Wait Expansion:** Increased parameters for non-golden window: attempts 3→15, wait 15-30s→30-60s, added 300s total timeout. Constants centralized in `logic/golden_hour.py`.

---

### v1.13 Golden Retry & Notification Accuracy — SHIPPED 2026-05-17
**Tests:** 740 passing
**Key accomplishments:**
- **Golden Retry Loop Optimization:** `_golden_retry_loop` now uses post-relist scan data (`_last_scan_result`) instead of stale pre-relist data. If no expired items remain after main relist, retry loop is skipped instantly (saves 9s of unnecessary waiting).
- **Golden Retry Loop Break Fix:** Fixed premature `break` condition (`if f == 0: break`) — loop now continues if `f == 0` but `remaining_processing > 0`, ensuring all Processing items in EA limbo are handled atomically within the golden window.
- **Telegram Report — No Double Counting:** `NotificationBatch.expired_detected` no longer sums expired counts across scans. Now uses the total processed (`relisted + failed`) as the base, preventing impossible counts (e.g., 132 scaduti when EA max is 100). Result is capped to actual Transfer List capacity.

---

### v1.14 Stale Data & Double Check Fixes — SHIPPED 2026-05-18
**Tests:** 740 passing
**Key accomplishments:**
- **Fix: Stale Telegram Notification After Reboot:** Notification batch was not reset before reboot. `flush_if_any(force=True)` sent stale data from previous cycles (e.g., "Relistati: 1" for a relist done hours earlier). Replaced with `batch.reset()` before reboot — stale data is silently discarded.
- **Fix: Missing 18:10 Telegram Notification:** Double redundant check in `flush_if_any()` was blocking notifications. `main.py:201` correctly checked `is_ready_to_flush(next_wait)`, but `flush_if_any()` internally rechecked with `is_ready_to_flush(0)` using hardcoded current_wait=0. After reboot, `last_flush_time` was `None` — none of 3 conditions passed. Replaced with `if not force and self.relisted == 0 and self.failed == 0: return`. The caller already verified conditions — internal check was redundant.

---

### v1.15 Golden Hour 16:10 Removal & Documentation Alignment — SHIPPED 2026-05-19
**Tests:** 740 passing
**Type:** Product Decision
**Key accomplishments:**
- **Golden Hour 16:10 RIMOSSA:** L'orario 16:10 non è più una golden hour attiva. Nessun relist tassativo alle 16:10. Restano solo 17:10 e 18:10 come picchi di relist (`GOLDEN_HOURS = (17, 18)`).
- **HOLD Period Clarified:** Il periodo HOLD inizia ufficialmente alle 16:10 — un'ora prima del primo picco 17:10, nessun relist forzato durante questo periodo.
- **Documentation Alignment:** Allineati tutti i file di planning (STATE.md, ROADMAP.md, PROJECT.md, CODEBASE.md) per riflettere la configurazione reale a 2 golden hours (non 3).
- **Phase 10 Completed:** Formalizzata la chiusura della Phase 10 (Stability & Notification Fixes) nei documenti di planning.

---

## Future Milestones

### v2.0 Enhanced Trading
**Status:** Planning
**Goal:** GUI
**Potential features:**
- Trading history and profit/loss statistics
- GUI interface (web dashboard)

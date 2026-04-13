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
- Golden Hour scheduling: 16:10/17:10/18:10 with pre-nav at :09:30

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

## Future Milestones

### v2.0 Enhanced Trading
**Status:** Planning
**Goal:** GUI
**Potential features:**
- Trading history and profit/loss statistics
- GUI interface (web dashboard)

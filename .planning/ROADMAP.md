# FIFA 26 Auto-Relist Tool - Roadmap

## Current Status: PRODUCTION / MAINTENANCE MODE
**Latest Milestone:** v1.3 Golden Hour Bug Fixes — SHIPPED 2026-04-12

## Phases

### Phase 1: Browser Setup & Authentication ✅ COMPLETED
**Goal:** Establish reliable browser automation and FIFA 26 WebApp login
**Requirements:** BROWSER-01, BROWSER-02, BROWSER-03
**Completed:** 2026-03-23

**Success Criteria:**
1. ✅ Playwright launches browser and navigates to FIFA 26 WebApp
2. ✅ User can authenticate with stored credentials
3. ✅ Session cookies persist across restarts
4. ✅ Browser handles login page detection

---

### Phase 2: Transfer Market Navigation ✅ COMPLETED (5/5 plans)
**Goal:** Navigate to My Listings and read listing state
**Requirements:** BROWSER-04, DETECT-01, DETECT-02, DETECT-03, DETECT-04
**Completed:** 2026-03-23

**Progress:**
| Plan | Name | Status | Commit |
|------|------|--------|--------|
| 00 | Test Infrastructure Setup | ✅ Complete | 4554109 |
| 01 | Listing Data Model | ✅ Complete | 85db6aa |
| 02 | Transfer Market Navigator | ✅ Complete | 2026-03-23 |
| 03 | DOM Detector | ✅ Complete | 2026-03-23 |
| 04 | Integration | ✅ Complete | 2026-03-23 |

**Success Criteria:**
1. ✅ System navigates to Transfer Market > My Listings
2. ✅ System identifies expired vs active listings
3. ✅ System reads player name, rating, price from each listing
4. ✅ System handles empty transfer list state

---

### Phase 3: Auto-Relist Core ✅ COMPLETED (3/3 plans)
**Goal:** Execute relisting actions on expired players
**Requirements:** RELIST-01, RELIST-02, RELIST-03, RELIST-04
**Completed:** 2026-04-08

Plans:
- [x] 03-00-PLAN.md — TDD: Price adjustment logic + RelistResult model ✅ 2026-03-23
- [x] 03-01-PLAN.md — RelistExecutor class with dialog handling ✅ 2026-03-23
- [x] 03-02-PLAN.md — Integration: wire relist into main.py ✅ 2026-04-08

**Success Criteria:**
1. ✅ System clicks relist on expired players
2. ✅ System applies configurable price adjustment
3. ✅ System confirms relisting action completed successfully
4. ✅ System handles confirmation dialogs

---

### Phase 4: Configuration System ✅ COMPLETED (3/3 plans)
**Goal:** User-configurable settings for pricing and timing
**Requirements:** CONFIG-01, CONFIG-02, CONFIG-03, CONFIG-04
**Completed:** 2026-03-23

Plans:
- [x] 04-00-PLAN.md — TDD: Config data model + validation tests ✅ 2026-03-23
- [x] 04-01-PLAN.md — ConfigManager class + CLI subcommands ✅ 2026-03-23
- [x] 04-02-PLAN.md — Integration: wire into main.py + human verify ✅ 2026-03-23

**Success Criteria:**
1. ✅ User can set listing duration
2. ✅ User can configure price rules (min/max/undercut)
3. ✅ User can set scan interval
4. ✅ Settings persist in JSON config file

---

### Phase 5: Logging & Error Handling ✅ COMPLETED (4/4 plans)
**Goal:** Robust operation with logging and error recovery
**Requirements:** LOG-01, LOG-02, LOG-03, LOG-04, ERROR-01, ERROR-02, ERROR-03, ERROR-04
**Completed:** 2026-03-23

Plans:
- [x] 05-00-PLAN.md — TDD: ActionLogEntry + RateLimiter + ErrorHandler ✅ 2026-03-23
- [x] 05-01-PLAN.md — Logging integration: JsonFormatter + history CLI ✅ 2026-03-23
- [x] 05-02-PLAN.md — Error recovery: wire rate limiter + session check + retry ✅ 2026-03-23
- [x] 05-03-PLAN.md — Console status with rich Live + final integration ✅ 2026-03-23

**Success Criteria:**
1. ✅ All relisting actions logged with timestamps
2. ✅ Real-time console status display
3. ✅ Network disconnection recovery
4. ✅ Session expiration handling (auto re-login)
5. ✅ Rate limiting between actions

---

### Phase 6: Telegram Bot Commands + Sold Items Cleanup ✅ COMPLETED (2/2 plans)
**Goal:** Interactive bot control via Telegram commands and automated sold items cleanup
**Requirements:** TELEGRAM-01 through TELEGRAM-10
**Completed:** 2026-04-06

Plans:
- [x] 06-00-PLAN.md — TDD: BotState + TelegramHandler + SoldHandler ✅ 2026-04-06
- [x] 06-01-PLAN.md — Integration: wire into main.py + human verify ✅ 2026-04-06

**Success Criteria:**
1. ✅ All 8 Telegram commands work
2. ✅ /pause stops scanning loop, browser stays open
3. ✅ /resume resumes scanning
4. ✅ /force_relist bypasses hold window and relists immediately
5. ✅ /screenshot sends current page screenshot
6. ✅ /del_sold navigates to Sold Items, collects credits, clears sold listings
7. ✅ /logs N sends last N lines of app.log
8. ✅ /status shows current bot state
9. ✅ /help shows available commands
10. ✅ Thread-safe communication between Telegram thread and main loop

---

### Phase 7: Bug Fixes & Stability ✅ COMPLETED
**Goal:** Fix critical golden hour bugs and improve reliability
**Requirements:** GOLDEN-FIX-01, GOLDEN-FIX-02, GOLDEN-FIX-03, POLLING-01
**Completed:** 2026-04-12

Fixes:
- [x] GOLDEN-FIX-01: Golden hour wait skips when already in :09-:11 window (commit 20da86e)
- [x] GOLDEN-FIX-02: EA popup dismissal between Transfers and Transfer List clicks (commit aa52cb3)
- [x] GOLDEN-FIX-03: Hold window override when no more goldens today (commit 20da86e)
- [x] POLLING-01: Ritardatari polling changed from 15-20s random to 10s fixed (commit fe2c2ea)
- [x] 519 timeline simulation tests added (tests/test_golden_timeline.py)

### Phase 8: Telegram Bugs ✅ COMPLETED
**Goal:** Fix /logs command not responding on subsequent invocations
**Completed:** 2026-04-13

Fixes:
- [x] /logs command offset bug — moved offset update to finally block so commands always get processed

**Success Criteria:**
1. ✅ Bot relists immediately at golden hour instead of waiting 59 min
2. ✅ EA popups no longer block Transfer List navigation
3. ✅ Expired items relisted after last golden when no more goldens remain
4. ✅ Ritardatari caught within 10s during golden windows
5. ✅ All 641 tests pass (122 original + 519 timeline)

---

## Shipped Milestones

| Version | Name | Date | Phases | Tests |
|---------|------|------|--------|-------|
| v1.0 | Auto-Relist MVP | 2026-03-23 | 1-5 | 68 |
| v1.1 | Telegram Commands & Sold Cleanup | 2026-04-06 | 6 | 112 |
| v1.2 | Protection & Stealth | 2026-04-11 | 6+ | 122 |
| v1.3 | Golden Hour Bug Fixes | 2026-04-12 | 7 | 641 |
| v1.4 | Telegram /logs Bug Fix | 2026-04-13 | 8 | 20 |

## Future Milestones

### v2.0 — Enhanced Trading
- Price monitoring and optimization
- Trading history and profit statistics
- GUI interface
- Multiple account support

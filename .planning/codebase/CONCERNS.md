# Codebase Concerns

**Analysis Date:** 2026-04-11

## Overview

This document identifies technical debt, known bugs, security considerations, and fragile areas in the FIFA 26 Auto-Relist Bot codebase.

---

## Technical Debt

### TD-001: Browser Crash During Golden Hour

**Issue:** The Playwright page/context can close unexpectedly during the critical golden hour window (16:10, 17:10, 18:10), causing a `TargetClosedError` crash.

**Files:** `main.py` (lines 754-833), `browser/detector.py`

**Impact:** Bot crashes at the exact moment when relist should execute. Lost listings during golden hours.

**Evidence (from logs/app.log, lines 2806-2832):**
```
2026-04-11 17:10:00,009 [ERROR] __main__: Errore: Page.query_selector: Target page, context or browser has been closed
  File "C:\App\fifa-relist\main.py", line 754, in main
    next_golden = get_next_golden_hour(now)
  File "C:\App\fifa-relist\browser\detector.py", line 154, in scan_listings
    empty_el = self.page.query_selector(SELECTORS["empty_state"])
playwright._impl._errors.TargetClosedError: Page.query_selector: Target page, context or browser has been closed
```

**Fix approach:** Add try-except around `detector.scan_listings()` with graceful recovery. Consider adding browser health check before golden window.

---

### TD-002: Telegram Polling 409 Conflict

**Issue:** Repeated `HTTP Error 409: Conflict` from Telegram getUpdates API, causing excessive debug logging.

**Files:** `telegram_handler.py`, `main.py`

**Impact:** Log spam (~100+ messages per minute during conflict), potential missed commands.

**Evidence (from logs/app.log, lines 2745-2780):**
```
2026-04-11 17:08:39,659 [DEBUG] telegram_handler: getUpdates fallito: HTTP Error 409: Conflict
```

**Fix approach:** Implement exponential backoff on 409 errors. Add deduplication. Consider using webhook instead of polling.

---

### TD-003: No Bounds Validation on Price Adjustment

**Issue:** `calculate_adjusted_price()` in `relist.py` does not validate that `adjustment_value` is within reasonable bounds before applying.

**Files:** `browser/relist.py` (lines 202-217)

**Impact:** Invalid config values (e.g., `adjustment_value: -50.0` for 50% discount) could cause negative prices or business logic errors.

**Evidence:**
```python
def calculate_adjusted_price(current_price: int, adjustment_type: str, adjustment_value: float, ...):
    if adjustment_type == "percentage":
        adjusted = current_price * (1 + adjustment_value / 100)
    elif adjustment_type == "fixed":
        adjusted = current_price + adjustment_value
    return max(min_price, min(max_price, int(adjusted)))
```

**Fix approach:** Add validation in `ConfigManager` to reject invalid `adjustment_value` ranges (e.g., -100% to +500% max).

---

### TD-004: Unbounded Command Queue in BotState

**Issue:** `_pending_commands` list in `bot_state.py` can grow unbounded if commands are added faster than processed.

**Files:** `bot_state.py` (lines 41, 95-110)

**Impact:** Memory leak in long-running sessions. Commands could be processed out of order or delayed indefinitely.

**Fix approach:** Add max queue size limit and TTL for stale commands.

---

### TD-005: Selector Fragility

**Issue:** CSS class selectors in `detector.py` and `relist.py` use hardcoded class names (e.g., `.listFUTItem`, `.auctionValue`, `.player-name`) that could change with EA WebApp updates.

**Files:** `browser/detector.py` (lines 13-23), `browser/relist.py` (lines 10-20)

**Impact:** Bot breaks silently when EA updates UI. No fallback selectors.

**Fix approach:** Add more selector variants as fallbacks. Consider using data attributes or more stable selectors.

---

## Known Bugs

### BUG-001: Session Recovery Not Attempted During Golden Window

**Symptom:** If session expires while bot is in golden hold loop (`_golden_hold_loop`), it returns to main loop but may not properly recover before the golden window closes.

**Files:** `main.py` (lines 536-581, 725-745)

**Trigger:** Session timeout during 15:10-18:15 hold period.

**Workaround:** None — requires manual restart.

---

### BUG-002: Heartbeat Can Close Page During Wait

**Symptom:** The heartbeat mechanism clicks "Clear Sold" which can cause issues if the page state changes unexpectedly.

**Files:** `main.py` (lines 464-533)

**Trigger:** During long waits (>1 hour), heartbeat click may fail or interfere with page.

**Workaround:** Exception is caught and logged as debug, but no recovery.

---

### BUG-003: Potential Race in get_next_golden_hour

**Symptom:** If system clock changes or timezone shifts, the golden hour calculation could become inconsistent mid-cycle.

**Files:** `main.py` (lines 288-303)

**Trigger:** Clock change during bot execution.

**Workaround:** None.

---

## Security Considerations

### SEC-001: Credentials in Environment Variables

**Risk:** FIFA_EMAIL and FIFA_PASSWORD stored in `.env` file on disk.

**Files:** `.env`, `main.py` (lines 113-120)

**Current mitigation:** `.env` is gitignored.

**Recommendations:** Consider using a secrets manager for production deployments. Add warning in README about `.env` file permissions.

---

### SEC-002: No Rate Limiting on Telegram Commands

**Risk:** A compromised Telegram bot token could allow attackers to send commands (pause, reboot, del_sold).

**Files:** `telegram_handler.py`, `bot_state.py`

**Current mitigation:** Commands processed sequentially with thread lock.

**Recommendations:** Add command authentication (e.g., whitelist chat_id for commands).

---

## Performance Bottlenecks

### PERF-001: Long Console Wait Blocks All Operations

**Problem:** When console session is active, bot sleeps for 30 minutes between checks (line 718 in main.py), but with max 4 hours wait.

**Files:** `main.py` (lines 142-162, 717-723)

**Cause:** Designed behavior for PS5/console compatibility, but blocks the bot completely.

**Improvement path:** Consider implementing a secondary check that runs faster (every 5 min) during console wait.

---

### PERF-002: Bulk DOM Extraction Can Fail Silently

**Problem:** The bulk `eval_on_selector_all` in `detector.py` can fail and fall back to per-element extraction without clear indication.

**Files:** `browser/dector.py` (lines 207-249)

**Cause:** Exception handling with fallback is good for resilience but makes performance unpredictable.

**Improvement path:** Add metrics/logging for fallback usage rate.

---

## Fragile Areas

### FRAG-001: main.py Main Loop

**Files:** `main.py` (lines 669-900)

**Why fragile:** 230+ lines in a single loop with many nested conditions. Golden hour logic, session recovery, notifications, wait calculations all intertwined.

**Safe modification:** Use the documented structure — always ensure `else` branch for normal relist when adding hold conditions.

**Test coverage gaps:** No integration tests for main loop. Unit tests only for individual functions.

---

### FRAG-002: AuthManager.is_console_session_active

**Files:** `browser/auth.py` (lines 145-193)

**Why fragile:** Multiple detection methods (retry button, dialog text, body text) that must work together. If one changes, detection fails.

**Safe modification:** Keep detection methods additive — add new checks rather than replace.

---

### FRAG-003: ListingDetector.scan_listings

**Files:** `browser/detector.py` (lines 151-307)

**Why fragile:** Complex DOM traversal with TreeWalker, section detection by position, bulk extraction with fallback. Many edge cases.

**Safe modification:** Any changes should preserve the fallback chain.

---

## Scaling Limits

### SCALE-001: Single Browser Instance

**Current capacity:** One Playwright browser instance, one page.

**Limit:** Cannot handle parallel transfer market operations. Cannot scan multiple accounts.

**Scaling path:** Implement multi-instance manager for parallel account handling (requires significant refactor).

---

### SCALE-002: Telegram Polling

**Current capacity:** Single polling thread with sequential command processing.

**Limit:** Commands processed one at a time. getUpdates limited to ~30 req/sec.

**Scaling path:** Consider webhooks for production scale.

---

## Dependencies at Risk

### DEP-001: Playwright

**Risk:** Browser automation is sensitive to EA WebApp changes. Playwright API is stable but EA's UI changes frequently.

**Impact:** Selector-based detection breaks when EA updates CSS.

**Migration plan:** Keep selectors in one place (`SELECTORS` dicts) for easy updates. Consider using `get_by_role()` more (already used in some places).

---

### DEP-002: python-dotenv

**Risk:** Low risk. Stable library.

**Impact:** None.

---

## Test Coverage Gaps

### GAP-001: No End-to-End Tests

**What's not tested:** Full bot flow from start to relist completion.

**Files:** `main.py`, `browser/*`

**Risk:** Integration issues between modules not caught.

**Priority:** Medium

---

### GAP-002: No Golden Hour Timing Tests

**What's not tested:** Precise timing of golden hour logic, hold window behavior.

**Files:** `main.py` (lines 288-349, 725-745)

**Risk:** Golden hour bugs discovered only at runtime.

**Priority:** High

---

### GAP-003: Session Recovery Tests

**What's not tested:** Recovery from various session failure modes.

**Files:** `browser/error_handler.py`, `main.py` (lines 389-406)

**Risk:** Recovery logic may have edge cases.

**Priority:** Medium

---

## Missing Critical Features

### MISS-001: Health Check Before Golden Window

**Problem:** Bot doesn't verify browser health before entering golden hold loop. If browser crashes during hold, it won't be detected until the next main loop iteration (after golden window passes).

**Blocks:** Reliable golden hour operation.

---

### MISS-002: Automatic Selector Validation

**Problem:** No way to detect if EA WebApp selectors have changed before running.

**Blocks:** Proactive monitoring of EA UI changes.

---

*Concerns audit: 2026-04-11*
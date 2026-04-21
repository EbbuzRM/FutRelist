# FIFA 26 Auto-Relist Tool - Requirements

## v1.0 Requirements — ALL COMPLETE ✅

### BROWSER - Browser Automation
- [x] **BROWSER-01**: User can launch automated browser session to FIFA 26 WebApp
- [x] **BROWSER-02**: User can authenticate with FIFA 26 credentials (stored securely)
- [x] **BROWSER-03**: System maintains session cookies across restarts
- [x] **BROWSER-04**: System navigates to Transfer Market > My Listings automatically

### DETECT - Listing Detection
- [x] **DETECT-01**: System detects when player listings have expired
- [x] **DETECT-02**: System reads player name, rating, and current listing price
- [x] **DETECT-03**: System distinguishes between active and expired listings
- [x] **DETECT-04**: System detects "no listings" state (empty transfer list)

### RELIST - Auto-Relisting
- [x] **RELIST-01**: System relists expired players with one-click action
- [x] **RELIST-02**: System applies configurable price adjustment (fixed or percentage)
- [x] **RELIST-03**: System confirms relisting action completed successfully
- [x] **RELIST-04**: System handles relist confirmation dialogs

### CONFIG - Configuration
- [x] **CONFIG-01**: User can configure default listing duration (1h, 3h, 6h, 12h, 24h, 3 days)
- [x] **CONFIG-02**: User can set price rules (min price, max price, undercut %)
- [x] **CONFIG-03**: User can configure scan interval (how often to check listings)
- [x] **CONFIG-04**: Configuration persists in JSON file

### LOG - Logging
- [x] **LOG-01**: System logs all relisting actions with timestamp
- [x] **LOG-02**: System logs errors and failures
- [x] **LOG-03**: System displays real-time status in console
- [x] **LOG-04**: User can view action history

### ERROR - Error Handling
- [x] **ERROR-01**: System recovers from network disconnections
- [x] **ERROR-02**: System handles session expiration (re-login)
- [x] **ERROR-03**: System handles UI element not found (page changes)
- [x] **ERROR-04**: System implements rate limiting (delays between actions)

## v1.1 Requirements — ALL COMPLETE ✅

### TELEGRAM - Telegram Bot Commands
- [x] **TELEGRAM-01**: Bot responds to /status command showing current bot state
- [x] **TELEGRAM-02**: Bot responds to /pause command to pause scanning (browser stays open)
- [x] **TELEGRAM-03**: Bot responds to /resume command to resume scanning
- [x] **TELEGRAM-04**: Bot responds to /force_relist command to bypass hold window and relist immediately
- [x] **TELEGRAM-05**: Bot responds to /screenshot command sending current page screenshot
- [x] **TELEGRAM-06**: Bot responds to /del_sold command navigating to Sold Items, collecting credits, clearing listings
- [x] **TELEGRAM-07**: Bot responds to /logs N command sending last N lines of app.log
- [x] **TELEGRAM-08**: Bot responds to /help command showing available commands
- [x] **TELEGRAM-09**: SoldHandler automates sold items navigation, credit collection, and cleanup
- [x] **TELEGRAM-10**: Thread-safe communication between Telegram thread and main loop

## v1.2 Requirements — ALL COMPLETE ✅

### PROTECT - Protection & Stealth
- [x] **PROTECT-01**: Console Mode — Deep Sleep via Telegram /console and /online commands
- [x] **PROTECT-02**: Heartbeat — dynamic 'Clear Sold' click every 2.5-5 min random to appear human
- [x] **PROTECT-03**: Automatic detection of manual relist during Golden Hours
- [x] **PROTECT-04**: Automatic handling of EA 'Cannot Authenticate' modal
- [x] **PROTECT-05**: Reboot command — /reboot triggers clean shutdown + subprocess respawn
- [x] **PROTECT-06**: Batch Telegram notifications — accumulates events within 120s

## v1.3 Requirements — ALL COMPLETE ✅

### GOLDEN-FIX - Golden Hour Bug Fixes
- [x] **GOLDEN-FIX-01**: Golden hour wait skips when already in :09-:11 window (commit 20da86e)
  - At 16:10 the bot waited 59 min until 17:10 instead of relisting immediately
  - Fixed by adding `is_in_golden_window(now)` check
- [x] **GOLDEN-FIX-02**: EA popup dismissal between Transfers and Transfer List clicks (commit aa52cb3)
  - `view-modal-container form-modal` intercepted pointer events for 30s causing timeout cascade
  - Fixed by adding `dismiss_popups()` + Escape + 3-attempt retry loop
- [x] **GOLDEN-FIX-03**: Hold window override when no more goldens today (commit 20da86e)
  - 61 expired items stuck at 18:14 waiting for non-existent 19:10 golden
  - Fixed by checking `get_next_golden_hour() is None` → override hold and relist immediately
- [x] **POLLING-01**: Ritardatari polling changed from 15-20s random to 10s fixed (commit fe2c2ea)
- [x] **TEST-01**: 519 timeline simulation tests covering every minute 14:00-20:59 + golden boundaries

## v1.10 Requirements — ALL COMPLETE ✅

### GOLDEN-STABILITY - Precise Timing & Stealth
- [x] **GOLDEN-STABILITY-01**: Force pre-navigation at exactly :09:00 (guard at :08:00)
- [x] **GOLDEN-STABILITY-02**: Long-sleep during HOLD periods (remove 60s cap)
- [x] **GOLDEN-STABILITY-03**: Heartbeat robustness (Escape + force click)
- [x] **GOLDEN-STABILITY-04**: Documentation lock in AGENTS.md

## Future Requirements (v2.0+)
- Price monitoring and optimization
- Trading history and profit statistics
- GUI interface
- Multiple account support
- Snipe mode (buy underpriced players)

## Out of Scope
- Real-money trading (RMT)
- Coin selling/buying
- Any form of cheating or exploitation
- Direct API access (uses browser automation only)

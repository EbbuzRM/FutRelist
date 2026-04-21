# FIFA 26 WebApp Auto-Relist Bot

## Core Value
Automated relisting of expired players on FIFA 26 WebApp transfer market, running continuously in background with Telegram control, golden hour scheduling, and anti-detection measures.

## Current Status: PRODUCTION
**Latest Release:** v1.10 Golden Stability & Session Heartbeat (2026-04-21)
**Test Suite:** 674 tests passing (148 unit + 526 golden timeline)
**Production Verified:** 53 items relisted, 0 failures, "Wait All Expired" logic confirmed

## Shipped Features

### Browser Automation
- Playwright-based browser controller with persistent profile (no repeated 2FA)
- EA login flow: email → NEXT → password → Sign in
- Session cookie persistence across restarts
- Popup dismissal (EA modals, form containers)

### Auto-Relist Engine
- DOM-based listing detection (active/expired/sold states)
- Configurable price adjustment: percentage or fixed, with FIFA bounds (200-15M)
- RelistExecutor: single item + batch relist with dialog confirmation
- Golden Hour scheduling: 16:10/17:10/18:10 with :09-:11 window
- Pre-navigation at :09:00 before each golden
- Hold window between goldens (expired items wait for next golden)
- Normal (immediate) relist outside golden period
- Ritardatari polling at 10s fixed during golden windows
- "Wait All Expired" logic: waits for all items (including "Processing") to expire before relisting outside golden periods

### Configuration
- ConfigManager with typed dataclasses (AppConfig, BrowserConfig, ListingDefaults, RateLimitingConfig)
- CLI subcommands: show/set/reset
- Deep-merge migration for config schema changes
- JSON persistence with unknown key preservation

### Telegram Control
- 8 commands: /status, /pause, /resume, /force_relist, /screenshot, /del_sold, /logs, /help
- Thread-safe BotState with pause/resume/force_relist/reboot flags
- SoldHandler: navigate to sold items, collect credits, clear listings
- Chat authentication (authorized chat_id only)
- Batch notifications: accumulates events within 120s, sends single summary
- Detailed Telegram reports: distinct counters for "Active (with timer)", "Expired detected", and "Just Relisted"

### Protection & Stealth
- Console Mode: Deep Sleep via /console and /online (minimizes browser activity)
- Heartbeat: dynamic 'Clear Sold' click every 2.5-5 min random
- Rate limiting: 2-5s random delays between actions
- EA modal auto-dismissal (Cannot Authenticate, form containers)
- Manual relist detection during Golden Hours

### Logging & Error Handling
- Structured JSONL logging (actions.jsonl) with ActionLogEntry + JsonFormatter
- Rich console output with timestamps (%H:%M:%S)
- CLI history subcommand for viewing action history
- Session expiry detection and automatic recovery
- Retry with exponential backoff (tenacity, 2-30s, max 3 attempts)
- Clean shutdown: browser close + Telegram handler stop + subprocess respawn

## Tech Stack
- **Language:** Python 3.13
- **Browser Automation:** Playwright (persistent profile, anti-detection)
- **CLI:** argparse with subcommands (run, config, history)
- **Notifications:** python-telegram-bot (long polling, chat auth)
- **Logging:** rich (console), python-json-logger (JSONL), standard logging (app.log)
- **Resilience:** tenacity (retry/backoff), python-dotenv (secrets)
- **Testing:** pytest (641 tests)

## Architecture
```
fifa-relist/
├── main.py              — Entry point, main loop, golden hour logic, auth
├── browser/
│   ├── controller.py    — Playwright wrapper with persistent profile
│   ├── auth.py          — EA login (2-step), session management
│   ├── navigator.py     — Home → Transfers → Transfer List, popup dismissal
│   ├── detector.py      — DOM scan for listings (state, price, timer)
│   ├── relist.py        — RelistExecutor (single + batch, price adjustment)
│   ├── rate_limiter.py  — Random delays (2-5s), from_config()
│   ├── error_handler.py — Session expiry, retry_on_timeout, ensure_session
│   └── sold_handler.py  — Sold items cleanup, credit collection
├── config/
│   ├── config.py        — Typed dataclasses (4), validation, from_dict/to_dict
│   └── config.json      — Runtime configuration
├── models/
│   ├── listing.py       — ListingState (ACTIVE/EXPIRED/PROCESSING/SOLD), PlayerListing, ListingScanResult
│   ├── relist_result.py — RelistResult, RelistBatchResult
│   ├── sold_result.py   — SoldCreditsResult
│   └── action_log.py    — ActionLogEntry, JsonFormatter, parse_action_history
├── notifier.py          — Telegram notifications (messages + screenshots)
├── bot_state.py         — Thread-safe BotState (pause/resume/force/reboot)
├── telegram_handler.py  — 8 command handlers, long polling, chat auth
└── tests/
    ├── test_*.py        — 122 unit/feature tests
    └── test_golden_timeline.py — 519 golden hour timeline simulations
```

## Constraints
- Must handle FIFA 26 WebApp authentication (2-step EA login)
- Rate limiting awareness (2-5s delays, avoid EA anti-bot detection)
- Session persistence across restarts (cookie-based)
- Error recovery for network/UI issues (retry + session check)
- Golden Hour logic is CRITICAL and must not be modified without explicit approval (see AGENTS.md)
- Every relist block MUST have an `else` fallback for normal relist

## Last Updated
2026-04-21

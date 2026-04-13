# FIFA 26 Auto-Relist Tool — Codebase Map

**Analysis Date:** 2026-04-13
**Project Root:** `C:\App\fifa-relist`
**Language:** Python 3.13
**Current Phase:** Phase 7+ (Stability & Detailed Reporting) — v1.4 shipped

---

## Directory Tree

```
fifa-relist/
├── main.py                 # Entry point — main loop, golden hour logic, CLI
├── bot_state.py            # Thread-safe state for remote control (pause, reboot, etc.)
├── telegram_handler.py     # Telegram bot via polling (/status, /pause, /resume, /reboot, etc.)
├── notifier.py             # Telegram alert helpers (batch notifications)
├── setup.py                # Package metadata
├── requirements.txt        # Python dependencies
├── browser/
│   ├── __init__.py         # Empty package marker
│   ├── controller.py       # Playwright browser lifecycle management
│   ├── auth.py             # Login flow + session persistence + console detection
│   ├── navigator.py        # Transfer Market navigation (Home → Transfers → Transfer List)
│   ├── detector.py         # DOM scanning for listings (active/expired/sold)
│   ├── relist.py           # Relist execution (single + all), price adjustment
│   ├── rate_limiter.py     # Random delay enforcement (2-5s anti-detection)
│   ├── error_handler.py    # Session expiry detection, retry logic, recovery
│   └── sold_handler.py     # Sold items cleanup and credit collection
├── config/
│   ├── config.py           # ConfigManager with typed dataclasses and validation
│   ├── config.json         # Runtime config (user-specific, gitignored)
│   └── config.example.json # Template for new users
├── models/
│   ├── listing.py          # ListingState, PlayerListing, ListingScanResult
│   ├── relist_result.py    # RelistResult, RelistBatchResult
│   ├── sold_result.py      # SoldCreditsResult
│   └── action_log.py       # ActionLogEntry, JsonFormatter, parse_action_history()
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # pytest fixtures (sample_listing_html, etc.)
│   ├── test_rate_limiter.py
│   ├── test_config.py
│   ├── test_detector.py
│   ├── test_bot_state.py
│   ├── test_action_log.py
│   ├── test_telegram_handler.py
│   ├── test_sold_handler.py
│   ├── test_error_handler.py
│   ├── test_relist.py
│   └── test_listing_model.py
├── storage/                 # Runtime-generated; stores session state
│   ├── browser_profile/    # Persistent browser profile (cookies, localStorage, IndexedDB)
│   ├── cookies.json        # Session cookies backup
│   └── browser_state.json  # Browser state JSON
├── logs/                    # Runtime logs (generated)
│   ├── app.log             # Application log (DEBUG level)
│   └── actions.jsonl       # Structured JSON action logs
└── .planning/               # GSD project management (not part of app)
    ├── PROJECT.md
    ├── REQUIREMENTS.md
    ├── ROADMAP.md
    ├── STATE.md
    ├── CODEBASE.md
    ├── MILESTONES.md
    ├── LOG.md
    └── codebase/
        ├── STACK.md
        ├── ARCHITECTURE.md
        ├── STRUCTURE.md
        ├── CONVENTIONS.md
        ├── CONCERNS.md
        ├── INTEGRATIONS.md
        └── TESTING.md
```

---

## Module Map

### `main.py` — Entry Point / Orchestrator / Main Loop

| Aspect | Detail |
|--------|--------|
| **Path** | `main.py` (1061+ lines) |
| **Responsibility** | Application bootstrap, golden hour logic, main scan loop, CLI commands |
| **Imports from project** | All browser modules, config, models, bot_state, telegram_handler, notifier |
| **External imports** | `json`, `logging`, `os`, `sys`, `argparse`, `threading`, `time`, `datetime` |
| **Key functions** | `main()` — entry point; `run()` — main loop; `setup_logging()`; `get_next_golden_hour()`; `is_in_hold_window()`; `ensure_session()`; CLI parsers |
| **Flow** | Load config → start browser → authenticate → Telegram handler start → loop: session check → golden sync → navigate → scan → relist decision → wait → repeat → graceful shutdown |
| **Connected to** | All modules |

### `browser/controller.py` — BrowserController

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/controller.py` |
| **Responsibility** | Playwright lifecycle, persistent context launch/close |
| **Class** | `BrowserController` |
| **External imports** | `playwright.sync_api` |
| **State** | `self.playwright`, `self.browser`, `self.context`, `self.page`, `self._is_running` |
| **Key methods** | `start() -> Page`; `navigate_to_webapp()`; `get_page() -> Page`; `stop()`; `is_running() -> bool` |
| **Config consumed** | `browser.headless`, `browser.slow_mo`, `fifa_webapp_url` |
| **Connected to** | `main.py`, `browser/auth.py` |

### `browser/auth.py` — AuthManager

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/auth.py` |
| **Responsibility** | Login flow, session persistence, console detection |
| **Class** | `AuthManager` |
| **External imports** | `playwright.sync_api.Page` |
| **Constants** | `SELECTORS` dict for login elements, main page detection |
| **Key methods** | `has_saved_session()`, `load_session()`, `save_session()`, `is_logged_in()`, `perform_login()`, `is_console_session_active()` |
| **Runtime files** | `storage/browser_profile/`, `storage/cookies.json` |
| **Connected to** | `main.py`, `browser/controller.py` |

### `browser/navigator.py` — TransferMarketNavigator

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/navigator.py` |
| **Responsibility** | Navigate to Transfer List |
| **Class** | `TransferMarketNavigator` |
| **Key methods** | `go_to_transfer_list()` — Home → Transfers → Transfer List with popup dismissal |
| **Config consumed** | `rate_limiting` (min/max delay ms) |
| **Connected to** | `main.py`, `browser/rate_limiter.py` |

### `browser/detector.py` — ListingDetector

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/detector.py` |
| **Responsibility** | DOM scanning, extract listings (active/expired/sold) |
| **Class** | `ListingDetector` |
| **Key methods** | `scan_listings()` → `ListingScanResult`; helpers: `parse_price()`, `parse_rating()`, `determine_state()` |
| **Pattern** | Bulk `eval_on_selector_all` with per-element fallback |
| **Connected to** | `main.py`, `models/listing.py` |

### `browser/relist.py` — RelistExecutor

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/relist.py` |
| **Responsibility** | Execute relist on expired listings, price adjustment |
| **Class** | `RelistExecutor` |
| **Key methods** | `relist_single()` → `RelistResult`; `relist_expired()` → `RelistBatchResult`; `calculate_adjusted_price()` |
| **Config consumed** | `listing_defaults.duration`, `price_adjustment_type`, `price_adjustment_value`, `min_price`, `max_price` |
| **Connected to** | `main.py`, `models/relist_result.py`, `browser/rate_limiter.py` |

### `browser/rate_limiter.py` — RateLimiter

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/rate_limiter.py` |
| **Responsibility** | Random delay enforcement (anti-detection) |
| **Class** | `RateLimiter` |
| **Key methods** | `wait()`; `wait_if_needed()`; `from_config(RateLimitingConfig)` |
| **Config consumed** | `rate_limiting.min_delay_ms`, `rate_limiting.max_delay_ms` |
| **Connected to** | `browser/navigator.py`, `browser/relist.py` |

### `browser/error_handler.py` — ErrorHandler

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/error_handler.py` |
| **Responsibility** | Session expiry detection, retry logic, recovery |
| **Functions** | `@retry_on_timeout` (decorator); `is_session_expired()`; `handle_element_not_found()`; `ensure_session()` |
| **Connected to** | `main.py`, `browser/auth.py` |

### `browser/sold_handler.py` — SoldHandler

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/sold_handler.py` |
| **Responsibility** | Navigate to sold items, collect credits, cleanup |
| **Class** | `SoldHandler` |
| **Key methods** | `go_to_sold_items()`, `collect_sold_credits()` → `SoldCreditsResult` |
| **Connected to** | `main.py`, `models/sold_result.py` |

### `bot_state.py` — BotState

| Aspect | Detail |
|--------|--------|
| **Path** | `bot_state.py` |
| **Responsibility** | Thread-safe state for remote control (pause, reboot, force_relist) |
| **Class** | `BotState` |
| **State** | `_is_paused`, `_force_relist`, `_reboot_event`, `_pending_commands`, stats |
| **Thread safety** | `threading.Lock` for all operations |
| **Connected to** | `main.py`, `telegram_handler.py` |

### `telegram_handler.py` — TelegramHandler

| Aspect | Detail |
|--------|--------|
| **Path** | `telegram_handler.py` |
| **Responsibility** | Telegram bot commands via long polling |
| **Class** | `TelegramHandler` |
| **Commands** | `/status`, `/pause`, `/resume`, `/force_relist`, `/del_sold`, `/logs`, `/reboot`, `/console`, `/online` |
| **Config consumed** | `notifications.telegram_token`, `notifications.telegram_chat_id` |
| **Connected to** | `main.py`, `bot_state.py`, `notifier.py` |

### `notifier.py` — Notifier

| Aspect | Detail |
|--------|--------|
| **Path** | `notifier.py` |
| **Responsibility** | Telegram alert helpers (batch notifications) |
| **Functions** | `_send_batch_notification()`, batch triggers: every 5 min or 5+ items |
| **Connected to** | `main.py`, `telegram_handler.py` |

### `config/config.py` — ConfigManager

| Aspect | Detail |
|--------|--------|
| **Path** | `config/config.py` |
| **Responsibility** | Typed configuration with validation |
| **Classes** | `AppConfig`, `BrowserConfig`, `ListingDefaults`, `RateLimitingConfig`, `ConfigManager` |
| **Key methods** | `load()`, `save()`, `set_value()`, `reset_defaults()`, `from_dict()`, `to_dict()` |
| **Config file** | `config/config.json` |
| **Validation** | `__post_init__` in each dataclass |
| **Connected to** | `main.py`, all modules |

### `models/listing.py` — Listing Data Models

| Aspect | Detail |
|--------|--------|
| **Path** | `models/listing.py` |
| **Classes** | `ListingState` (enum: ACTIVE, EXPIRED, PROCESSING, SOLD); `PlayerListing`; `ListingScanResult` |
| **Connected to** | `browser/detector.py`, `main.py` |

### `models/relist_result.py` — Relist Result Models

| Aspect | Detail |
|--------|--------|
| **Path** | `models/relist_result.py` |
| **Classes** | `RelistResult`, `RelistBatchResult` with `from_results()` factory |
| **Connected to** | `browser/relist.py`, `main.py` |

### `models/action_log.py` — Action Logging

| Aspect | Detail |
|--------|--------|
| **Path** | `models/action_log.py` |
| **Classes** | `ActionLogEntry`; `JsonFormatter` (custom logging formatter); `parse_action_history()` |
| **Connected to** | `main.py`, logging setup |

---

## Data Flow — Main Execution Path

```
main.py::run()
  │
  ├─ setup_logging()          → logs/app.log + console + actions.jsonl
  ├─ load_config()            ← ConfigManager.load() → config/config.json
  ├─ get_credentials()       ← env vars or .env file
  │
  ├─ BrowserController.start()
  │   └─ launch_persistent_context() → storage/browser_profile/
  │
  ├─ AuthManager
  │   └─ is_logged_in()? → perform_login() → save_session()
  │
  ├─ TelegramHandler.start()  → polling thread
  │
  └─ Main Scan Loop (while running):
      │
      ├─ bot_state.is_paused? → sleep 10s, continue
      │
      ├─ ensure_session()     → verify/recover session validity
      │
      ├─ Golden Hour Sync:
      │   ├─ is_in_golden_period()? (15:10-18:15)
      │   ├─ is_in_hold_window()? → hold until :10
      │   └─ pre-nav at :09:30 before each golden
      │
      ├─ navigator.go_to_transfer_list()
      │   └─ RateLimiter.wait_if_needed()
      │
      ├─ detector.scan_listings() → ListingScanResult
      │   └─ active_count, expired_count, sold_count
      │
      ├─ Relist Decision:
      │   ├─ expired > 0 AND (not in hold OR force_relist) → relist
      │   │   └─ relist_executor.relist_expired()
      │   │       └─ RateLimiter.wait() between each
      │   └─ active > 0 → compute wait from min_active_seconds
      │
      ├─ Wait Calculation:
      │   ├─ Polling mode: sync_minute - 60s trigger
      │   ├─ Golden mode: wait until :10 precise
      │   └─ Normal mode: min_active_seconds + jitter
      │
      ├─ notifier.send_batch()  → every 5 min or 5+ items
      │
      └─ Loop → repeat from session check
```

### Reboot Flow (`/reboot` command)
```
TelegramHandler → bot_state._reboot_event.set()
Main loop → wait_interruptible() unblocks → break loop
         → cleanup (browser stop, telegram stop)
         → subprocess.Popen([sys.executable, main.py])
         → sys.exit(0)
```

---

## External Dependencies

From `requirements.txt`:

| Package | Version | Purpose |
|---------|---------|---------|
| `playwright` | >= 1.40.0 | Browser automation (Chromium control, selectors, navigation) |
| `python-dotenv` | >= 1.0.0 | .env file loading (credentials) |
| `tenacity` | >= 8.0 | Retry decorator for transient failures |
| `rich` | >= 13.0 | Terminal UI with tables and formatting |
| `pytest` | >= 7.0.0 | Unit testing framework |

---

## Architecture Notes

### Pattern
**Event-driven polling loop with browser automation** — Continuous scan cycle with dynamic wait intervals, golden hour synchronization, thread-safe state management.

### Layer Structure
```
┌─────────────────────────────────────────────────────────────┐
│  main.py (Orchestrator)                                     │  ← main loop, CLI, golden hour logic
├─────────────────────────────────────────────────────────────┤
│  bot_state.py          │  telegram_handler.py  │ notifier.py│  ← remote control & notifications
├─────────────────────────────────────────────────────────────┤
│  browser/controller.py │ browser/auth.py       │ browser/* │  ← Playwright lifecycle + EA WebApp
├─────────────────────────────────────────────────────────────┤
│  config/config.py      │  models/*.py          │            │  ← typed config, domain models
├─────────────────────────────────────────────────────────────┤
│  config/config.json    │  storage/*.json       │ logs/      │  ← runtime state
└─────────────────────────────────────────────────────────────┘
```

### What's Implemented (Phase 1–6)
- ✅ Playwright browser launch with persistent context
- ✅ Login detection + automation + session persistence
- ✅ Transfer Market navigation (Home → Transfers → Transfer List)
- ✅ DOM scanning for listings (active/expired/sold)
- ✅ Relist execution with price adjustment
- ✅ Golden Hour logic (16:10, 17:10, 18:10 with hold window)
- ✅ Rate limiting enforcement (2-5s delays)
- ✅ Session expiry detection and recovery
- ✅ Action logging (JSONL structured)
- ✅ Telegram notifications (batch every 5 min or 5+ items)
- ✅ Telegram commands (/status, /pause, /resume, /force_relist, /del_sold, /logs, /reboot, /console)
- ✅ Sold items cleanup (SoldHandler)
- ✅ Reboot command with subprocess respawn
- ✅ "Wait All Expired" logic (waits for processing items before relisting)
- ✅ Detailed Telegram reports (Active with timer vs. Expired vs. Just Relisted)

### Key Selectors (in `browser/detector.py` and `browser/relist.py`)
- `.listFUTItem` — player listing container
- `.auctionValue` — price element
- `.player-name` — player name
- State detection: English ("Expired", "Active") and Italian ("Scaduto", "Attivo")

---

## Risks & Observations

### Technical Debt (from CONCERNS.md)

1. **TD-001: Browser Crash During Golden Hour** — `TargetClosedError` can crash bot at critical :10 moments. Fix: Add try-except around `detector.scan_listings()` with recovery.

2. **TD-002: Telegram Polling 409 Conflict** — `HTTP Error 409` causes log spam. Fix: Exponential backoff on 409 errors.

3. **TD-003: No Bounds Validation on Price Adjustment** — `adjustment_value` not validated before use. Fix: Add validation in ConfigManager.

4. **TD-004: Unbounded Command Queue in BotState** — `_pending_commands` can grow unbounded. Fix: Add max queue size limit.

5. **TD-005: Selector Fragility** — Hardcoded CSS class selectors can break on EA UI updates. Fix: Add fallback selectors.

### Known Bugs (from CONCERNS.md)

- **BUG-001: Session Recovery Not Attempted During Golden Window** — Session expires during hold loop may not recover properly.
- **BUG-002: Heartbeat Can Close Page During Wait** — Long wait heartbeat click may fail.
- **BUG-003: Potential Race in get_next_golden_hour** — Clock changes during execution could cause inconsistency.

### Security Considerations

- **SEC-001: Credentials in .env** — Stored on disk, gitignored but not encrypted. Consider secrets manager.
- **SEC-002: No Rate Limiting on Telegram Commands** — Compromised token allows control. Consider chat_id whitelist.

### Test Coverage Gaps

- **GAP-001: No End-to-End Tests** — Full bot flow not tested.
- **GAP-002: No Golden Hour Timing Tests** — Precise timing only discovered at runtime.
- **GAP-003: Session Recovery Tests** — Various failure modes not tested.

### Scaling Limits

- **SCALE-001: Single Browser Instance** — Cannot handle parallel operations or multiple accounts.
- **SCALE-002: Telegram Polling** — Single thread, sequential command processing.

---

*Codebase map: 2026-04-13 — v1.4 shipped, ~20 source files, ~2500+ lines of application code.*
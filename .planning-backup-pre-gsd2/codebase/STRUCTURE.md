# Codebase Structure

**Analysis Date:** 2026-04-12

## Directory Layout

```
C:\App\fifa-relist\
├── main.py                 # Entry point, main loop, CLI (~1060 lines)
├── bot_state.py            # Thread-safe state for remote control
├── telegram_handler.py     # Telegram bot commands via polling
├── notifier.py             # Telegram alert helpers
├── setup.py                # Package metadata
├── browser/                # Playwright automation modules
├── config/                 # Configuration management
├── models/                 # Data models
├── tests/                  # Unit tests
└── logs/                   # Runtime logs (generated)
```

## Directory Purposes

**browser/:**
- Purpose: All browser automation logic
- Contains: controller.py, auth.py, navigator.py, detector.py, relist.py, rate_limiter.py, error_handler.py, sold_handler.py
- Key files: `controller.py` (Playwright lifecycle), `detector.py` (DOM scanning), `relist.py` (relist execution)

**config/:**
- Purpose: Configuration loading and validation
- Contains: config.py (ConfigManager, typed dataclasses), config.json (runtime config)
- Key files: `config.py` (281 lines)

**models/:**
- Purpose: Domain data structures
- Contains: listing.py, relist_result.py, sold_result.py, action_log.py
- Key files: `listing.py` (ListingState, PlayerListing, ListingScanResult)

**tests/:**
- Purpose: Unit tests with pytest (641 total)
- Contains: test_*.py files, conftest.py
- Key file: `test_golden_timeline.py` (519 golden hour timeline simulation tests)
- Run with: `pytest`

## Key File Locations

**Entry Points:**
- `main.py`: Primary entry (run mode, config subcommands, history)
- `main.py:583`: main() function

**Configuration:**
- `config/config.py`: ConfigManager and typed config classes
- `config/config.json`: Runtime configuration (user-specific)
- `config/config.example.json`: Template for new users

**Core Logic:**
- `browser/controller.py`: Browser lifecycle and persistent session
- `browser/detector.py`: DOM scanning and listing extraction
- `browser/relist.py`: Relist execution logic
- `main.py`: Golden hour logic and main scan loop

**Testing:**
- `tests/conftest.py`: pytest fixtures
- `tests/test_*.py`: Unit tests for each module
- `tests/test_golden_timeline.py`: 519 golden hour timeline simulation tests

## Naming Conventions

**Files:**
- snake_case: `bot_state.py`, `telegram_handler.py`
- Module prefix for related code: `browser/*.py`

**Functions:**
- snake_case: `get_next_golden_hour()`, `is_in_hold_window()`
- Verb-noun pattern: `scan_listings()`, `perform_login()`

**Classes:**
- PascalCase: `BrowserController`, `ListingDetector`, `RelistExecutor`

**Constants:**
- UPPER_SNAKE: `GOLDEN_HOURS`, `GOLDEN_MINUTE`, `GOLDEN_PRE_NAV_MINUTE`

## Where to Add New Code

**New Feature:**
- Primary code: `main.py` (if orchestration) or new module in `browser/` (if browser logic)
- Tests: `tests/test_*.py`

**New Browser Module:**
- Implementation: `browser/new_module.py`
- Import from: `from browser.new_module import NewClass`

**Utilities:**
- Shared helpers: Consider adding to existing modules (e.g., rate_limiter.py for timing, detector.py for parsing)

## Special Directories

**storage/:**
- Purpose: Browser profile persistence
- Generated: Yes (created on first run)
- Committed: No (in .gitignore)

**logs/:**
- Purpose: Runtime logs (app.log, actions.jsonl)
- Generated: Yes (created at runtime)
- Committed: No (in .gitignore)

**config/config.json:**
- Purpose: Runtime user configuration
- Generated: Yes (created on first run)
- Committed: No (in .gitignore) - contains secrets

---

*Structure analysis: 2026-04-12*
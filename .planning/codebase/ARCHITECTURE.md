# Architecture

**Analysis Date:** 2026-04-12

## Pattern Overview

**Overall:** Event-driven polling loop with browser automation

**Key Characteristics:**
- Continuous scan cycle with dynamic wait intervals
- Golden Hour synchronization at specific times (16:10, 17:10, 18:10)
- Thread-safe state management for Telegram integration
- Persistent browser session with profile-based storage

## Layers

**Orchestration (main.py):**
- Purpose: Main entry point and control loop
- Location: `main.py` (1060 lines)
- Contains: CLI parser, logging setup, golden hour logic, main scan loop
- Depends on: All browser modules, config, models, notifier, telegram_handler
- Used by: Direct execution (`python main.py run`)

**Browser Automation (browser/):**
- Purpose: All Playwright interactions with EA WebApp
- Location: `browser/`
- Contains: Controller, Auth, Navigator, Detector, Relist, RateLimiter, ErrorHandler, SoldHandler
- Depends on: Playwright, config dict, models
- Used by: main.py orchestration layer

**Configuration (config/):**
- Purpose: Typed configuration with validation
- Location: `config/config.py`
- Contains: AppConfig, BrowserConfig, ListingDefaults, RateLimitingConfig, ConfigManager
- Depends on: JSON config files
- Used by: All modules that need configuration

**Data Models (models/):**
- Purpose: Domain objects for listings, results, action logs
- Location: `models/`
- Contains: ListingState, PlayerListing, ListingScanResult, RelistResult, ActionLog
- Depends on: None (pure data)
- Used by: Detector, RelistExecutor, main.py

**State & Integration (bot_state.py, telegram_handler.py, notifier.py):**
- Purpose: Remote control and notifications
- Location: Root level
- Contains: BotState (thread-safe state), TelegramHandler (polling commands), notifier (Telegram alerts)
- Depends on: threading, urllib, json
- Used by: main.py for remote control

## Data Flow

**Main Scan Cycle:**

1. **Initialize** → Load config → Start browser → Authenticate
2. **Session Check** → `ensure_session()` verifies validity
3. **Golden Sync** → If in golden period (15:10-18:15) and not in relist window, hold until :10. If already in golden window (:09-:11), skip sleep and relist immediately.
4. **Navigate** → `navigator.go_to_transfer_list()` reaches Transfer List
5. **Scan** → `detector.scan_listings()` reads DOM, returns ListingScanResult
6. **Decision** → 
   - If expired > 0 AND (not in hold OR force_relist): execute relist
   - If no expired: compute optimal wait based on active timers
7. **Wait** → Dynamic wait calculated from `min_active_seconds` or golden timing
8. **Loop** → Repeat from step 2

**State Synchronization:**
- Telegram commands (pause, reboot, force_relist) set flags in BotState
- Main loop checks BotState flags each cycle
- Command queue for thread-unsafe operations (del_sold)

## Key Abstractions

**ListingDetector (browser/detector.py):**
- Purpose: DOM scanning and parsing of Transfer List
- Examples: `scan_listings()` → `ListingScanResult`
- Pattern: DOM selectors + text parsing + state classification

**RelistExecutor (browser/relist.py):**
- Purpose: Execute relist actions on expired listings
- Examples: `relist_single()`, `relist_all()`, `check_session_valid()`
- Pattern: Modal handling, price adjustment calculation

**BrowserController (browser/controller.py):**
- Purpose: Playwright lifecycle and persistent session
- Examples: `start()`, `navigate_to_webapp()`, `stop()`
- Pattern: launch_persistent_context for cookie/session persistence

**AuthManager (browser/auth.py):**
- Purpose: Login flow and session detection
- Examples: `perform_login()`, `is_logged_in()`, `is_console_session_active()`
- Pattern: Two-step login (email→NEXT→password→Sign in), 2FA handling, console detection

## Entry Points

**main():**
- Location: `main.py` line 583
- Triggers: Direct execution (`python main.py` or `python main.py run`)
- Responsibilities: Init → Auth → Loop → Reboot handling

**CLI Subcommands:**
- Location: `main.py` line 965 (build_parser)
- Triggers: `python main.py config show`, `python main.py history -n 20`
- Responsibilities: Config management, action history viewing

## Error Handling

**Strategy:** Layered recovery with escalation

**Patterns:**
- Session expiry: Reload + re-authenticate (in `error_handler.py`)
- Console detection: Wait loop (30 min checks, max 4 hours)
- Navigation timeout: Retry with page reload
- Navigation blocked by popup: 3-attempt retry with `dismiss_popups()` + Escape key (in `navigator.py`)
- Relist errors: Check for error banner, session validation

## Cross-Cutting Concerns

**Logging:** Dual output (file + console) with action_logger for JSON structured logs

**Validation:** Config validation in `config/config.py` dataclasses

**Authentication:** Persistent profile storage to avoid repeated 2FA

---

*Architecture analysis: 2026-04-12*
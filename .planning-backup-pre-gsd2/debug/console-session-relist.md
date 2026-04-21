---
status: investigating
trigger: "The user reports that the bot performed relisting actions while they were actively using the EA Console. Logs show the bot detected the 'Retry' button (Console Session), but instead of stopping, it proceeded to relist items."
created: 2026-04-18T10:00:00Z
updated: 2026-04-18T10:00:00Z
---

## Current Focus

hypothesis: The console session detection mechanism (Retry button) identifies the state but does not effectively block the execution flow in `main.py` or `browser/relist.py`.
test: Trace the "Retry" button detection from `auth.py`/`error_handler.py` to the relist execution block in `main.py`.
expecting: Finding a path where the bot detects the console session but fails to exit the loop or bypass the relist logic.
next_action: Search codebase for "Retry" button detection logic.

## Symptoms

expected: Bot must stop all relisting actions immediately if a Console Session (Retry button) is detected to avoid ban risk.
actual: Bot detects 'Retry' button but continues to execute `relist_all()` or `relist_single()`.
errors: User reported "Relisting during Console Session".
reproduction: User active on EA Console while bot is running.
started: Reported recently.

## Eliminated

## Evidence

- timestamp: 2026-04-18T10:15:00Z
  checked: `browser/auth.py`
  found: `is_console_session_active(page)` correctly detects the "Retry" button and returns `True`.
  implication: Detection logic is working; the issue is in how this signal is used to block actions.

- timestamp: 2026-04-18T10:16:00Z
  checked: `main.py`
  found: `authenticate()` handles console sessions by waiting 1800s, but this is ONLY during the authentication phase. Once `authenticate()` returns, the main loop starts.
  implication: The main loop relies on `keeper.supervise_state()` and `keeper.ensure_session()` to maintain safety.

- timestamp: 2026-04-18T10:17:00Z
  checked: `browser/session_keeper.py`
  found: `supervise_state()` checks `bot_state.is_console_mode()`, but this is a manual/scheduled mode set via Telegram, NOT a real-time detection of the "Retry" button. `_execute_heartbeat()` detects the console session but only logs a warning: `logger.warning("Heartbeat ha rilevato la console in uso!")`.
  implication: Real-time detection of a console session does NOT trigger a state change in `bot_state` and does NOT stop the bot.

- timestamp: 2026-04-18T10:18:00Z
  checked: `browser/error_handler.py`
  found: `ensure_session()` calls `authenticate()`, which DOES handle console sessions. However, `ensure_session` is called at the START of the cycle. If a console session starts AFTER `ensure_session` but BEFORE `engine.process_cycle`, the bot will proceed.
  implication: There is a gap between session verification and action execution.

- timestamp: 2026-04-18T10:19:00Z
  checked: `logic/relist_engine.py`
  found: `process_cycle()` does NOT check `auth.is_console_session_active()` before calling `_execute_relist_with_verification()`.
  implication: The core relist logic has no "fail-fast" check for console sessions.
## Resolution

root_cause: The bot lacks a real-time "fail-fast" check for console sessions immediately before executing relist actions. While detection exists in `auth.py`, it is primarily used during the initial authentication phase or as a passive warning during heartbeats. Specifically, `RelistEngine.process_cycle` and `RelistExecutor` do not verify the absence of a console session (Retry button) before interacting with the DOM to relist items. If a user logs into the console after the bot has passed the `ensure_session` check but before the relist click, the bot proceeds, creating the ban-risk scenario.

fix: (Goal was find_root_cause_only)

verification: (Goal was find_root_cause_only)

files_changed: [
  "main.py",
  "browser/session_keeper.py",
  "logic/relist_engine.py",
  "browser/relist.py"
]

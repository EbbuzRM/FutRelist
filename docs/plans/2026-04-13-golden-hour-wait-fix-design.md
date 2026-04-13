# Design Document: Golden Hour Wait Fix

**Date:** 2026-04-13
**Author:** Trae AI
**Status:** Approved by User

## Problem Statement

The bot currently experiences a "blindness" issue when started during a Golden Hour HOLD period (e.g., at 17:21). Although it now navigates to the Transfer List correctly on Cycle 1, it immediately enters a blocking `time.sleep()` for the remaining time until the Golden Hour (e.g., 48 minutes).

This causes:
1. **Inactivity:** No heartbeats are sent, risking session expiration.
2. **Unresponsiveness:** Telegram commands are ignored for the duration of the sleep.
3. **Missed Expirations:** The bot "sleeps" before scanning, thus missing items that expire *before* the Golden Hour (e.g., an item with 47 minutes remaining at 17:21).

## Proposed Design

### 1. Window-Based Precision Wait
The exact precision wait (down to the second) should only occur when we are very close to the Golden Hour (e.g., within the `GOLDEN_CLOSE_WINDOW` of :08-:12).
- **Condition:** Only trigger the precision sleep if `is_close_to_golden(now)` is True.
- **Outcome:** At 17:21, the bot will skip the precision wait, proceed to scan the Transfer List, and then enter a normal `HOLD` state (Home page) with heartbeats.

### 2. Interruptible Precision Wait
Replace `time.sleep()` with `bot_state.wait_interruptible()` throughout the precision wait logic.
- **Benefit:** This allows the bot to wake up instantly if a Telegram command is queued, even during the final seconds before a Golden Hour.

### 3. Cycle 1 Full Scan Enforcement
Maintain the fix that forces Cycle 1 to always perform a full scan (navigation + detection) even during HOLD windows. This ensures the bot always has the "ground truth" before entering passive HOLD.

## Data Flow & Components

- **main.py**: Update the `--- WAIT FOR EXACT GOLDEN TIME ---` block to include the `is_close_to_golden` guard and use `wait_interruptible`.
- **bot_state.py**: (Already updated) `wait_interruptible` now handles both reboot and command events.

## Verification Plan

### Automated Tests
- Update `tests/test_golden_timeline.py` (if necessary) to verify that at 17:21 the bot does not "over-wait" but proceeds to scan.

### Manual Verification
- Start the bot at a non-golden time (e.g., 17:21) and verify:
  1. It navigates to the Transfer List.
  2. It scans and logs active items (e.g., "47 min remaining").
  3. It enters HOLD (Home page) and sends heartbeats.
  4. It responds to Telegram commands during the HOLD period.

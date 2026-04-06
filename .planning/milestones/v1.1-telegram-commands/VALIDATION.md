# Validation Criteria: Telegram Commands & Sold Cleanup

## Automated Validation

### Unit Tests
1. **BotState tests** (`tests/test_bot_state.py`):
   - Initial state: paused=False, force_relist=False
   - set_paused(True/False) updates state correctly
   - set_force_relist(True/False) updates state correctly
   - Thread safety: concurrent reads/writes don't corrupt state
   - get_status() returns formatted dict

2. **Telegram command parsing tests** (`tests/test_telegram_handler.py`):
   - `/status` → returns status message
   - `/pause` → sets paused=True
   - `/resume` → sets paused=False
   - `/force_relist` → sets force_relist=True
   - `/help` → returns help text
   - `/logs 10` → returns last 10 log lines
   - `/logs` → returns last 20 log lines (default)
   - Unknown command → returns "Unknown command" message
   - Command from unauthorized chat_id → ignored

3. **Sold handler tests** (`tests/test_sold_handler.py`):
   - SoldCreditsResult model: total_credits, items_cleared
   - parse_sold_credits() extracts credit values from DOM data

### Integration Validation (Human Verify)

1. **All 8 commands work via Telegram**:
   - Send each command, verify response
   - Verify /logs accepts numeric argument

2. **/pause stops scanning loop**:
   - Send /pause
   - Verify bot stops scanning (no new log entries)
   - Verify browser stays open

3. **/resume resumes scanning**:
   - Send /resume after /pause
   - Verify bot resumes scanning (new log entries appear)

4. **/force_relist bypasses hold window**:
   - During hold window, send /force_relist
   - Verify expired listings are relisted immediately

5. **/screenshot sends current page**:
   - Send /screenshot
   - Verify photo received in Telegram

6. **/del_sold clears sold items**:
   - Send /del_sold
   - Verify sold items are cleared
   - Verify credits total reported

7. **/status shows current state**:
   - Send /status
   - Verify shows: paused/resumed, cycle count, last scan, relist counts

8. **/help shows commands**:
   - Send /help
   - Verify all 8 commands listed with descriptions

9. **Thread-safe communication**:
   - Send commands while bot is scanning
   - Verify no race conditions or crashes

## File Existence Checks
- `telegram_handler.py` exists with TelegramHandler class
- `bot_state.py` exists with BotState dataclass
- `browser/sold_handler.py` exists with SoldHandler class
- `main.py` imports and starts Telegram thread
- `main.py` checks BotState.paused in loop
- `main.py` checks BotState.force_relist in loop

## Constraint Verification
- Golden hour logic NOT modified (verify with git diff)
- detector.py NOT modified
- navigator.py NOT modified
- relist.py NOT modified (core logic)
- No new dependencies in requirements.txt (urllib only)
- Rate limiting preserved (2-5s delays)

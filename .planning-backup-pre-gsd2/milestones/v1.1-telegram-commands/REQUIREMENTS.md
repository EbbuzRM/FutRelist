# Requirements: Telegram Commands & Sold Cleanup

## Milestone: v1.1 — Telegram Commands & Sold Items Cleanup

### TELEGRAM-01: Bot Commands Handler Module
- Create `telegram_handler.py` as new module
- Polling Telegram updates in background thread
- Uses urllib (no extra dependencies) for Telegram Bot API
- Thread-safe communication with main bot loop

### TELEGRAM-02: BotState Shared State
- Create `bot_state.py` with BotState dataclass
- Thread-safe state management (threading.Lock)
- State fields: paused (bool), force_relist (bool), last_command (str), stats (dict)

### TELEGRAM-03: /status Command
- Show current bot state: paused/resumed, cycle count, last scan time, relist counts
- Send formatted message via Telegram

### TELEGRAM-04: /pause and /resume Commands
- /pause stops the scanning loop, browser stays open
- /resume resumes the scanning loop
- State persisted in BotState

### TELEGRAM-05: /force_relist Command
- Bypasses hold window and relists immediately
- Sets force_relist flag in BotState
- Flag consumed and reset by main loop

### TELEGRAM-06: /screenshot Command
- Captures current browser page
- Sends screenshot via Telegram sendPhoto API

### TELEGRAM-07: /del_sold Command
- Navigate to Sold Items page
- Collect credits from sold items (read prices)
- Clear sold listings (click "Clear Sold Items" or equivalent)
- Report total credits recovered

### TELEGRAM-08: /logs Command
- Accept optional N parameter (default: 20)
- Read last N lines from `logs/app.log`
- Send as formatted Telegram message

### TELEGRAM-09: /help Command
- Show available commands with descriptions
- Formatted message with all 8 commands

### TELEGRAM-10: Integration into main.py
- Start Telegram handler thread after authentication
- Check BotState.paused in main loop (skip scan if paused)
- Check BotState.force_relist (bypass hold window)
- Graceful shutdown of Telegram thread on Ctrl+C

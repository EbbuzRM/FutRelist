# Research: Telegram Bot API Patterns

## Telegram Bot API (urllib-based)

### Base URL
```
https://api.telegram.org/bot{TOKEN}/{METHOD}
```

### Key Methods Used

#### sendMessage
```
POST https://api.telegram.org/bot{TOKEN}/sendMessage
Content-Type: application/json

{
  "chat_id": "{CHAT_ID}",
  "text": "Message text",
  "parse_mode": "HTML"  // optional
}
```

#### sendPhoto
```
POST https://api.telegram.org/bot{TOKEN}/sendPhoto
Content-Type: multipart/form-data

- chat_id: {CHAT_ID}
- photo: (file)
- caption: "Optional caption"
```

#### getUpdates (Polling)
```
GET https://api.telegram.org/bot{TOKEN}/getUpdates?offset={OFFSET}&timeout=30

Returns:
{
  "ok": true,
  "result": [
    {
      "update_id": 123456,
      "message": {
        "message_id": 1,
        "from": {"id": 12345, "username": "user"},
        "chat": {"id": 12345},
        "date": 1234567890,
        "text": "/command"
      }
    }
  ]
}
```

### Polling Pattern
- Use `getUpdates` with `offset` parameter to avoid re-processing
- `timeout` parameter for long polling (30s recommended)
- Track `offset = last_update_id + 1`
- Run in background thread to not block main loop

### Command Parsing
- Messages starting with `/` are commands
- Format: `/command arg1 arg2`
- Split on space: `parts = text.split()`, `command = parts[0]`, `args = parts[1:]`

### Thread Safety Pattern
- Use `threading.Lock` for shared state
- BotState holds mutable state (paused, force_relist)
- Main loop reads state, Telegram handler writes state
- Lock protects all reads/writes to shared state

### Error Handling
- Network errors: retry with exponential backoff
- Rate limits: Telegram allows 30 messages/second, 20 messages/minute to same chat
- Invalid token: fail fast with clear error

### Existing Project Pattern (notifier.py)
- Already uses urllib.request for Telegram API
- `send_telegram_alert()` for text messages
- `send_telegram_photo()` for screenshots with multipart/form-data
- These can be reused or extended

### Background Thread Pattern
```python
import threading
import time

class TelegramHandler:
    def __init__(self, token, chat_id, bot_state, page):
        self.token = token
        self.chat_id = chat_id
        self.bot_state = bot_state
        self.page = page  # Playwright page for screenshot
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _poll(self):
        offset = 0
        while not self._stop_event.is_set():
            updates = self._get_updates(offset)
            for update in updates:
                self._handle_update(update)
                offset = update["update_id"] + 1
            time.sleep(1)  # poll interval
```

### Constraints
- NO extra dependencies (use urllib, not python-telegram-bot or aiogram)
- Thread-safe with threading.Lock
- Compatible with existing notifier.py patterns
- Rate limiting preserved (2-5s delays for browser actions)

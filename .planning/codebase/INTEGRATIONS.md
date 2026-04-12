# External Integrations

**Analysis Date:** 2026-04-11

## APIs & External Services

**FIFA WebApp (Target):**
- EA Sports FIFA 26 WebApp - Primary automation target
  - URL: `https://www.ea.com/fifa/ultimate-team/web-app/`
  - Technology: Browser automation via Playwright
  - Authentication: Email + Password via EA login flow
  - Session: Persisted browser profile to avoid re-authentication

**Telegram Bot API (Notification & Control):**
- Telegram Bot API - Notifications and remote commands
  - SDK/Client: Native `urllib` (no external telegram library)
  - Endpoints:
    - `https://api.telegram.org/bot{TOKEN}/sendMessage`
    - `https://api.telegram.org/bot{TOKEN}/sendPhoto`
    - `https://api.telegram.org/bot{TOKEN}/getUpdates`
  - Config: `notifications.telegram_token` and `notifications.telegram_chat_id`
  - Features:
    - Batch notifications every 5 minutes or 5+ items relisted
    - Remote control: `/status`, `/pause`, `/resume`, `/force_relist`, `/del_sold`, `/logs`, `/reboot`, `/console`

**Telegram Handler Implementation** (`telegram_handler.py`):
- Long polling with offset tracking
- Commands processed in main thread (queued)
- Markdown formatting for responses

## Data Storage

**Browser State:**
- Persistent browser profile: `storage/browser_profile`
  - Contains: Cookies, localStorage, sessionStorage, IndexedDB
  - Purpose: Avoid 2FA on subsequent runs

**Session Backup:**
- `storage/cookies.json` - Saved cookies for session restoration

## Authentication & Identity

**FIFA EA Account:**
- Implementation via Playwright browser automation
- Credentials stored in `.env`:
  ```
  FIFA_EMAIL=your_email@example.com
  FIFA_PASSWORD=your_password_here
  ```
- Session persistence via browser profile (no 2FA after first login)
- Console session detection: Warns when PS5/console player is active

**Telegram Bot:**
- Token-based authentication
- Chat ID authorization (only whitelisted chat can send commands)
- Configured in `config/config.json`

## Monitoring & Observability

**Logging:**
- File logging: `logs/app.log` (DEBUG level)
- Action logging: `logs/actions.jsonl` (JSON structured)
- Console logging: INFO level via `rich` library

**Error Tracking:**
- In-app error handling with screenshots saved on failure
- Telegram alerts for critical errors

## CI/CD & Deployment

**Hosting:**
- Local execution (desktop/laptop)
- No cloud deployment

**CI Pipeline:**
- None detected

**Setup Scripts:**
- `setup.py` - Interactive setup (Python)
- `setup.bat` - Windows setup
- `setup.sh` - Unix setup

## Environment Configuration

**Required env vars:**
- `FIFA_EMAIL` - EA account email
- `FIFA_PASSWORD` - EA account password
- `TELEGRAM_BOT_TOKEN` (optional) - For notifications
- `TELEGRAM_CHAT_ID` (optional) - For notifications

**Secrets location:**
- `.env` file (NOT committed to git)
- `config/config.json` (NOT committed for production)
- `.gitignore` excludes: `.env`, `config/config.json`, `storage/`

**Config files in gitignore:**
```
.env
config/config.json
storage/
logs/
```

## Webhooks & Callbacks

**Incoming:**
- Telegram long polling (handler.py `_poll()` method)
- Updates fetched via `getUpdates` API every 30 seconds
- No webhooks (uses polling, not push)

**Outgoing:**
- Telegram sendMessage, sendPhoto APIs for notifications
- EA FIFA WebApp interactions (browser automation)

---

*Integration audit: 2026-04-11*
# Phase 5: Logging & Error Handling - Research

**Researched:** 2026-03-23
**Domain:** Python structured logging, Playwright error recovery, CLI status display, rate limiting
**Confidence:** HIGH

## Summary

Phase 5 adds production-grade logging (structured JSON action log, real-time console status, action history) and error recovery (network retry with backoff, session re-login, UI element fallback, rate limiting) to the existing FIFA auto-relist tool.

The project already has a working `setup_logging()` in main.py with file + console handlers and Italian-language log messages throughout. Phase 5 enhances this foundation rather than replacing it. The `RateLimitingConfig` dataclass exists but `_random_delay()` in navigator/relist only uses basic `time.sleep` with random range — no actual enforcement or backoff strategy.

**Primary recommendation:** Use Python stdlib `logging` with a custom `JsonFormatter` for the action log file, `tenacity` for retry/backoff, and `rich` for real-time console status. Wrap Playwright calls in a retry-aware error handler that catches `TimeoutError` and `Error` from `playwright.sync_api`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| logging (stdlib) | 3.13 | Structured action logging + app logging | Zero deps, battle-tested, already in project |
| json (stdlib) | 3.13 | JSON serialization for action log entries | Zero deps, project already uses for config |
| tenacity | >=8.0 | Retry with exponential backoff | De facto standard for Python retry; Apache 2.0; 96 code snippets on Context7 |
| rich | >=13.0 | Real-time console status (Live/Progress) | Best-in-class for CLI status; stdlib alternative would be fragile ANSI codes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses (stdlib) | 3.13 | ActionLogEntry model | Already used in project (relist_result.py, config.py) |
| pathlib (stdlib) | 3.13 | Log file path management | Already used in project |
| datetime (stdlib) | 3.13 | Timestamps in ISO format | Already used in project |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | Manual retry loops | Tenacity gives exponential backoff, jitter, stop conditions in 3 lines; manual is 20+ lines and error-prone |
| rich Live/Progress | ANSI escape codes + print | Rich is cross-platform, handles terminal resize, auto-refresh; ANSI codes break on Windows and need manual clearing |
| structlog | Custom JsonFormatter | structlog adds processing pipeline overhead; a 30-line JsonFormatter class covers our needs (stdlib only) |
| python-json-logger | Custom JsonFormatter | Adds a dependency for what stdlib can do in 30 lines; no advantage for our simple JSON lines format |

**Installation:**
```bash
pip install tenacity rich
```

Also add to requirements.txt:
```
tenacity>=8.0
rich>=13.0
```

## Architecture Patterns

### Recommended Project Structure
```
browser/
├── controller.py      # BrowserController (existing)
├── auth.py            # AuthManager (existing)
├── navigator.py       # TransferMarketNavigator (existing)
├── detector.py        # ListingDetector (existing)
├── relist.py          # RelistExecutor (existing)
├── error_handler.py   # NEW: RetryHandler, error classification
└── rate_limiter.py    # NEW: RateLimiter class
config/
├── config.py          # AppConfig (existing)
models/
├── listing.py         # (existing)
├── relist_result.py   # RelistResult (existing)
├── action_log.py      # NEW: ActionLogEntry dataclass
logs/
├── app.log            # Human-readable log (existing)
├── actions.jsonl      # NEW: Structured JSON action log (one JSON per line)
main.py                # Enhanced setup_logging(), status display, history subcommand
tests/
├── test_error_handler.py  # NEW: retry/backoff tests
├── test_rate_limiter.py   # NEW: rate limiting tests
├── test_action_log.py     # NEW: action log model + JSON formatter tests
└── conftest.py            # (existing)
```

### Pattern 1: Custom JsonFormatter for Action Log
**What:** A `logging.Formatter` subclass that emits one JSON object per line (JSONL format) to a dedicated file handler.
**When to use:** Every relist action and error gets logged as structured JSON to `logs/actions.jsonl`.
**Example:**
```python
# Source: Python stdlib logging + web research 2026-02-12
import json
import logging
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line with UTC ISO timestamp."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields passed via logger.info("...", extra={...})
        if hasattr(record, "action"):
            log_data["action"] = record.action
        if hasattr(record, "player_name"):
            log_data["player_name"] = record.player_name
        if hasattr(record, "success"):
            log_data["success"] = record.success
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)
```

### Pattern 2: Retry with Exponential Backoff (tenacity)
**What:** Decorate Playwright navigation/action functions with `@retry` for automatic retry on transient failures.
**When to use:** Network errors, timeouts, and UI element not found during navigation and relist actions.
**Example:**
```python
# Source: Context7 /jd/tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

@retry(
    retry=(retry_if_exception_type(PlaywrightError) | retry_if_exception_type(PlaywrightTimeoutError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
    before_sleep=lambda rs: logger.warning(
        f"Tentativo {rs.attempt_number} fallito: {rs.outcome.exception()}. "
        f"Riprovo tra {rs.next_action.sleep:.1f}s..."
    ),
)
def navigate_with_retry(page, url):
    page.goto(url, wait_until="networkidle", timeout=30000)
```

### Pattern 3: Real-Time Console Status with Rich
**What:** Use `rich.live.Live` with a `rich.table.Table` that updates during scan/relist cycles.
**When to use:** During the main loop: show scan status, relist progress, error count.
**Example:**
```python
# Source: Rich docs - rich.readthedocs.io/en/latest/live.html
from rich.live import Live
from rich.table import Table

def make_status_table(phase: str, scanned: int, relisted: int, errors: int) -> Table:
    table = Table(title="FIFA Auto-Relist")
    table.add_column("Fase", style="cyan")
    table.add_column("Scansionati", justify="right")
    table.add_column("Rilistati", justify="right", style="green")
    table.add_column("Errori", justify="right", style="red")
    table.add_row(phase, str(scanned), str(relisted), str(errors))
    return table

# In main loop:
with Live(make_status_table("In attesa...", 0, 0, 0), refresh_per_second=2) as live:
    # After each action:
    live.update(make_status_table("Scansione", scanned=15, relisted=3, errors=0))
```

### Pattern 4: Rate Limiter Class
**What:** Centralized rate limiter that enforces `RateLimitingConfig` delays with jitter between actions.
**When to use:** Replace scattered `_random_delay()` calls with a single `RateLimiter` instance passed to navigator/relist.
**Example:**
```python
import random
import time
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Enforce rate limiting between actions with configurable delay range."""

    def __init__(self, min_delay_ms: int = 2000, max_delay_ms: int = 5000):
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self._last_action_time: float = 0

    def wait(self) -> None:
        """Wait for the configured delay with random jitter."""
        delay_ms = random.randint(self.min_delay_ms, self.max_delay_ms)
        delay_s = delay_ms / 1000.0
        logger.debug(f"Rate limit: attesa {delay_ms}ms")
        time.sleep(delay_s)
        self._last_action_time = time.time()

    def wait_if_needed(self) -> None:
        """Only wait if not enough time has passed since last action."""
        elapsed = time.time() - self._last_action_time
        min_s = self.min_delay_ms / 1000.0
        if elapsed < min_s:
            remaining = min_s - elapsed
            logger.debug(f"Rate limit: attesa residua {remaining:.1f}s")
            time.sleep(remaining)
```

### Pattern 5: Session Expiry Detection
**What:** Check `auth.is_logged_in(page)` before each scan cycle. If session expired, trigger re-login flow.
**When to use:** At the start of each scan loop iteration, or when a Playwright `TimeoutError` suggests the page is stuck on login.
**Example:**
```python
def ensure_session(page, auth, controller):
    """Check session validity, re-login if expired."""
    if not auth.is_logged_in(page):
        logger.warning("Sessione scaduta, tentativo di re-login...")
        auth.delete_saved_session()
        page.reload()
        page.wait_for_timeout(3000)
        if not auth.wait_for_login_page(page):
            raise RuntimeError("Impossibile raggiungere la pagina di login dopo sessione scaduta")
        email, password = get_credentials()
        if auth.perform_login(page, email, password):
            auth.save_session(controller.context)
            logger.info("Re-login completato")
            return True
        raise RuntimeError("Re-login fallito")
    return True
```

### Anti-Patterns to Avoid
- **Catching bare `except Exception` everywhere:** Classify errors (network vs. UI vs. auth) and handle each appropriately. A network error gets retry; a session error gets re-login.
- **Scattering `_random_delay()` across classes:** Centralize in `RateLimiter` so config changes propagate everywhere.
- **Using `print()` for status updates:** Use `rich.console.print()` or `rich.live.Live` so status doesn't collide with logging output.
- **Logging sensitive data (passwords, cookies):** Never log credentials. Log action outcomes and error messages only.
- **Building a custom retry loop:** tenacity handles exponential backoff, jitter, stop conditions, and logging callbacks in a declarative way.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Manual while-loop with sleep counter | tenacity `@retry` decorator | Exponential backoff, jitter, stop conditions, before_sleep logging — all declarative |
| JSON log formatting | Manual `json.dumps()` in every log call | Custom `logging.Formatter` subclass | Single source of truth, works with all handlers, stdlib only |
| Console status display | ANSI escape codes + `\r` + `os.system('cls')` | `rich.live.Live` with Table | Cross-platform, handles terminal resize, auto-refresh, doesn't break log output |
| Action history viewing | Custom file parser | `json.loads()` per line of `.jsonl` file | JSONL is the standard for structured log lines; Python can iterate lines easily |
| Rate limiting delays | `time.sleep(random.randint(...))` in each class | `RateLimiter` class with `wait()` | Single config source, testable, consistent behavior |

**Key insight:** The retry and status display domains have mature, battle-tested solutions (tenacity, rich). Custom implementations would miss edge cases (terminal resize, jitter distribution, retry state management) that these libraries handle correctly.

## Common Pitfalls

### Pitfall 1: Playwright Exception Types Not Imported Correctly
**What goes wrong:** Using `except Exception` catches everything including `KeyboardInterrupt`-adjacent errors. Playwright has specific exception types.
**Why it happens:** `playwright._impl._api_types` is an internal module — not the public API.
**How to avoid:** Import from `playwright.sync_api`:
```python
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Error as PlaywrightError
```
**Warning signs:** Generic `except Exception` blocks, seeing `_impl` in import paths.

### Pitfall 2: JSON Formatter Wrapping JSON in Extra Text
**What goes wrong:** The file handler's `logging.Formatter("%(asctime)s ... %(message)s")` wraps the JSON output from `JsonFormatter` in extra text, producing invalid JSON.
**Why it happens:** Each handler has its own formatter. If the file handler uses a text formatter but receives JSON-formatted messages, the output is mangled.
**How to avoid:** The JSON file handler must use `JsonFormatter`, and the console handler keeps the existing text `Formatter`. They are independent.
**Warning signs:** Log lines like `2026-03-23 ... {"timestamp": ...}` — text wrapping JSON.

### Pitfall 3: Rate Limiting Not Enforced Between Scan Cycles
**What goes wrong:** Delays only happen within `relist_single()` but not between the scan→relist→wait→scan loop.
**Why it happens:** `RateLimiter.wait()` is called in relist but the outer loop in `main()` doesn't call it.
**How to avoid:** Call `rate_limiter.wait()` at the end of each scan cycle iteration, outside of individual relist actions.
**Warning signs:** Rapid successive scans with no delay between them.

### Pitfall 4: Session Expiry Detection at Wrong Level
**What goes wrong:** Only checking `is_logged_in()` at startup, not during the loop.
**Why it happens:** Login check is in `main()` before the loop, but sessions can expire mid-run.
**How to avoid:** Call `ensure_session()` at the start of each scan cycle, wrapped in try/except for re-login failure.
**Warning signs:** Automation runs fine for first cycle, then fails with "element not found" on second cycle (because it's on login page).

### Pitfall 5: Rich Live Display Colliding with Logging
**What goes wrong:** `logging.StreamHandler(sys.stdout)` and `rich.live.Live` both write to stdout, causing garbled output.
**Why it happens:** Both compete for the same terminal.
**How to avoid:** Use `rich.console.Console` for the live display and either (a) use `rich.logging.RichHandler` instead of `StreamHandler`, or (b) redirect the logging `StreamHandler` to write through `live.console.print()` during live display.
**Warning signs:** Flickering, overlapping text, broken progress display.

## Code Examples

### Playwright Exception Handling Pattern
```python
# Source: playwright.dev/python/docs/api/class-timeouterror
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

try:
    page.locator("button:has-text('Relist')").click(timeout=5000)
except PlaywrightTimeoutError:
    logger.warning("Pulsante Relist non trovato nel timeout")
    # Attempt recovery: reload page and retry
except Exception as e:
    logger.error(f"Errore imprevisto: {e}")
```

### Structured Action Logging
```python
# Log a relist action as structured JSON
action_logger = logging.getLogger("actions")
action_logger.info(
    "Rilist completato",
    extra={
        "action": "relist",
        "player_name": "Mbappé",
        "old_price": 50000,
        "new_price": 45000,
        "success": True,
    },
)
# Output: {"timestamp": "2026-03-23T12:00:00+00:00", "level": "INFO", "logger": "actions", "message": "Rilist completato", "action": "relist", "player_name": "Mbappé", "success": true}
```

### Action History CLI Subcommand
```python
def show_history(lines: int = 20):
    """Display recent action history from actions.jsonl."""
    log_path = Path(__file__).parent / "logs" / "actions.jsonl"
    if not log_path.exists():
        print("Nessuna cronologia azioni trovata.")
        return
    with open(log_path, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f.readlines()[-lines:]]
    for entry in entries:
        ts = entry.get("timestamp", "?")
        msg = entry.get("message", "")
        status = "✓" if entry.get("success") else "✗"
        print(f"[{ts}] {status} {msg}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `print()` for status | `rich.live.Live` with Table | rich 10.0+ (2022) | Cross-platform, non-blocking, auto-refresh |
| Manual retry loops | `tenacity` @retry decorator | tenacity 6.0+ (2019) | Declarative, handles backoff/jitter/stop |
| Plain text log files | JSON lines (.jsonl) format | Industry standard by 2024 | Machine-parseable, queryable, aggregation-ready |
| `time.sleep()` scattered | Centralized `RateLimiter` class | Best practice pattern | Single config source, testable |

**Deprecated/outdated:**
- `playwright._impl._api_types.TimeoutError` → Use `playwright.sync_api.TimeoutError` (public API)
- `logging.config.fileConfig()` with .ini files → Use `logging.config.dictConfig()` with JSON
- ANSI escape codes for terminal formatting → Use `rich` for cross-platform support

## Open Questions

1. **Should `rich` be optional or required?**
   - What we know: `rich` adds a dependency but provides best-in-class console status.
   - What's unclear: Whether the project wants zero optional dependencies or is OK adding rich.
   - Recommendation: Required dependency. The alternative (ANSI codes) is fragile on Windows and requires ~50 lines of manual terminal control. `rich` is mature, stable, and widely used.

2. **Should the action log use a separate logger or the same logger with a different handler?**
   - What we know: Python logging supports multiple handlers on the same logger, or separate loggers.
   - What's unclear: Whether to use `logging.getLogger("actions")` for the JSON log vs. adding a second handler to the root logger.
   - Recommendation: Use a dedicated `actions` logger with its own `FileHandler` + `JsonFormatter`. This keeps the app.log human-readable and actions.jsonl machine-parseable. They serve different purposes.

3. **How should session re-login interact with headless mode?**
   - What we know: `get_credentials()` in main.py currently uses `input()` for interactive prompt.
   - What's unclear: If running headless, the `input()` call would fail or hang.
   - Recommendation: If credentials are available via env vars (`FIFA_EMAIL`, `FIFA_PASSWORD`), use them automatically. Only fall back to `input()` if env vars are missing AND not headless. This is already partially handled by `get_credentials()`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0.0 |
| Config file | None (default pytest discovery) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOG-01 | Structured JSON logging for relist actions | unit | `pytest tests/test_action_log.py -x` | ❌ Wave 0 |
| LOG-02 | Error/failure logging with structured context | unit | `pytest tests/test_action_log.py::test_error_log_entry -x` | ❌ Wave 0 |
| LOG-03 | Real-time console status display | integration | Manual verification (terminal output) | N/A — manual |
| LOG-04 | Action history viewing via CLI subcommand | unit | `pytest tests/test_action_log.py::test_history_parsing -x` | ❌ Wave 0 |
| ERROR-01 | Network disconnection recovery with backoff | unit | `pytest tests/test_error_handler.py::test_retry_backoff -x` | ❌ Wave 0 |
| ERROR-02 | Session expiration handling (auto re-login) | unit | `pytest tests/test_error_handler.py::test_session_expiry_detection -x` | ❌ Wave 0 |
| ERROR-03 | UI element not found recovery | unit | `pytest tests/test_error_handler.py::test_element_not_found_fallback -x` | ❌ Wave 0 |
| ERROR-04 | Rate limiting enforcement | unit | `pytest tests/test_rate_limiter.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_action_log.py` — covers LOG-01, LOG-02, LOG-04 (JsonFormatter, ActionLogEntry model, history parsing)
- [ ] `tests/test_error_handler.py` — covers ERROR-01, ERROR-02, ERROR-03 (retry logic, session detection, element fallback)
- [ ] `tests/test_rate_limiter.py` — covers ERROR-04 (RateLimiter wait, wait_if_needed, config integration)
- [ ] `models/action_log.py` — ActionLogEntry dataclass for structured log entries
- [ ] `browser/error_handler.py` — RetryHandler with tenacity integration
- [ ] `browser/rate_limiter.py` — RateLimiter class
- [ ] Framework install: `pip install tenacity rich` — not in current requirements.txt

## Sources

### Primary (HIGH confidence)
- Context7 `/jd/tenacity` — retry decorator patterns, exponential backoff, reraise, before_sleep callback (96 code snippets)
- Context7 `/microsoft/playwright-python` — TimeoutError import path, page events, wait_for_selector (91 code snippets)
- Rich docs `rich.readthedocs.io/en/latest/live.html` — Live display, refresh_per_second, console.print integration
- Rich docs `rich.readthedocs.io/en/latest/progress.html` — Progress bars, SpinnerColumn, task tracking
- Python stdlib `logging.Formatter` — Custom formatter subclass pattern (verified in Python 3.13 docs)

### Secondary (MEDIUM confidence)
- WebSearch 2026-02-12: "Python JSON Logging zero dependencies" — Custom JsonFormatter pattern using stdlib only
- WebSearch 2026-02-17: Structured JSON logging with Python — OneUptime blog, Google Cloud Logging patterns
- WebSearch 2026-03-01: structlog vs stdlib comparison — structlog fills processing pipeline gap, not needed for simple JSON
- WebSearch 2025-04-23: Playwright session expiry detection — Reddit thread on page.route() for 401 interception

### Tertiary (LOW confidence)
- WebSearch: Playwright `Error` class import path verified via playwright.dev docs and GitHub issue #860

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tenacity and rich are proven, stdlib logging is well-documented
- Architecture: HIGH — Patterns follow existing project conventions (dataclass, navigator, config dict)
- Pitfalls: HIGH — Playwright exception types verified via official docs and GitHub issues; JSON formatter pattern verified via multiple 2026 sources

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (30 days — tenacity and rich are stable; Playwright API is stable)

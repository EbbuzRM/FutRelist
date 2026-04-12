# Coding Conventions

**Analysis Date:** 2026-04-11

## Naming Patterns

**Files:**
- Modules: `snake_case.py` (e.g., `rate_limiter.py`, `action_log.py`)
- Test files: `test_<module_name>.py` (e.g., `test_rate_limiter.py`)
- Config: `config.py`, `listing.py`, `action_log.py`

**Functions:**
- snake_case with verb prefix: `get_credentials()`, `authenticate()`, `relist_expired_listings()`
- Helper functions prefixed with underscore: `_send_batch_notification()`, `_compute_next_wait()`

**Variables:**
- snake_case: `min_delay_ms`, `max_delay_ms`, `scan_interval_seconds`
- Private variables prefixed with underscore: `_is_running`, `_config`

**Classes:**
- PascalCase: `BrowserController`, `ListingDetector`, `RateLimiter`, `AppConfig`
- Exception classes with `Error` suffix: `AuthError`

**Constants:**
- SCREAMING_SNAKE: `GOLDEN_HOURS`, `EA_WEBAPP_URL`, `VALID_DURATIONS`
- Module-level grouping in `# ---------------------------------------------------------------------------` sections

**Types:**
- Enum values: `UPPER_SNAKE`: `ListingState.ACTIVE`, `ListingState.EXPIRED`

## Code Style

**Type Hints:**
- Function signatures: `def func() -> None:`, `def func(x: str) -> bool:`
- Return types union: `-> tuple[int, int]`, `-> datetime | None`
- Attribute types in dataclasses: `headless: bool = False`
- Import for type checking: `from typing import TYPE_CHECKING`

**Docstrings:**
- Simple module docstring at file top
- Function docstrings for complex functions (multi-line, description + args)
```python
def format_duration(seconds: int) -> str:
    """Formatta i secondi in stringa leggibile (es. '18 min', '1 min 30 s')."""
```

**Formatting:**
- Black not detected - manual formatting with 4-space indentation
- Line length: ~100 chars target (visible in editor)
- Imports organized in sections:
  1. Standard library (`import logging`, `import time`)
  2. Third-party (`from dotenv import load_dotenv`, `from rich.console import Console`)
  3. Local modules (`from browser.controller import BrowserController`)

**Imports:**
```python
from __future__ import annotations  # Enable PEP 563 postponed evaluation
```

## Error Handling

**Patterns:**
- Custom exceptions: `AuthError` in `browser/auth.py`
- Graceful degradation with try/except blocks
- Error propagation with context:
```python
except Exception as e:
    raise AuthError(f"Recupero sessione fallito in modo inatteso: {e}") from e
```

**Retry decorator:**
- Exponential backoff in `browser/error_handler.py`:
```python
def retry_on_timeout(func: Callable | None = None, *, max_retries: int = 3) -> Callable:
    """Decorator: retry a function up to max_retries times on Playwright timeout errors."""
    # Uses 2**attempt delay (1s, 2s, 4s)
```

**Error checking:**
- Session validity checks in `browser/error_handler.py`
- Element not found handling with fallback reload

**Flow control:**
- Fail-fast validation in `__post_init__`:
```python
def __post_init__(self):
    if self.duration not in VALID_DURATIONS:
        raise ValueError(f"duration must be one of {VALID_DURATIONS}, got '{self.duration}'")
```

## Logging Conventions

**Framework:** Python stdlib `logging`

**Logger setup:**
```python
action_logger = logging.getLogger("actions")
logger = logging.getLogger(__name__)
fifa_logger = logging.getLogger("fifa")
```

**Handlers:**
- File handler with DEBUG level: `logs/app.log`
- Console handler with INFO level: stdout
- JSONL structured logging: `logs/actions.jsonl`

**Format:**
- File: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- Console: `"[%(asctime)s] [%(levelname)s] %(message)s"` (datefmt: `%H:%M:%S`)

**Levels:**
- `logger.debug()`: Non-critical operational details
- `logger.info()`: Normal operation flow
- `logger.warning()`: Recoverable issues (timeouts, retrials)
- `logger.error()`: Failures requiring attention

**Context logging:**
- Use `extra={}` parameter for structured fields:
```python
action_logger.info(
    "Rilist completato",
    extra={"action": "relist", "player_name": result.player_name, "success": True},
)
```

**JSON Formatter:**
- Custom `JsonFormatter` in `models/action_log.py` for JSONL output
- Includes: timestamp, level, logger name, message, extra fields

## Dataclass Patterns

**Validation:**
- Use `@dataclass` with `__post_init__` for validation:
```python
@dataclass
class ListingDefaults:
    relist_mode: str = "all"
    duration: str = "1h"

    def __post_init__(self):
        if self.relist_mode not in VALID_RELIST_MODES:
            raise ValueError(f"relist_mode must be one of...")
```

**Factory methods:**
```python
@classmethod
def empty(cls) -> ListingScanResult:
    """Crea un risultato vuoto (nessun listing)."""
    return cls(...)
```

**Immutable patterns:**
- `field(default_factory=list)` for mutable defaults

## Configuration

**Approach:**
- Dataclass-based config in `config/config.py`
- JSON serialization with `to_dict()` / `from_dict()`
- Deep merge for config migration
- Unknown fields preserved as raw JSON

## Browser Automation

**Selectors:**
- Prefer `get_by_role()` for accessibility:
```python
page.get_by_role("button", name="Login")
page.get_by_role("button", name="Clear Sold Items")
```

**Wait strategies:**
- `page.wait_for_timeout(ms)` for fixed waits
- `is_visible(timeout=ms)` for element visibility
- `wait_until="domcontentloaded"` for page loads

**Context:**
- Persistent context for session reuse:
```python
self.playwright.chromium.launch_persistent_context(
    user_data_dir=str(profile_path),
    headless=browser_cfg.get("headless", False),
)
```

---

*Convention analysis: 2026-04-11*
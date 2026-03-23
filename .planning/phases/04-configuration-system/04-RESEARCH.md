# Phase 4: Configuration System - Research

**Researched:** 2026-03-23
**Domain:** Python JSON configuration management, CLI settings interface, config validation
**Confidence:** HIGH

## Summary

Phase 4 implements user-configurable settings for the FIFA 26 Auto-Relist tool. The project already has a working `config/config.json` with basic settings and a `load_config()` function in `main.py`. Phase 4 needs to: (1) expose all user-facing settings (listing duration, price rules, scan interval) via a structured config schema, (2) add validation to prevent invalid values, (3) enable saving config changes back to JSON, and (4) provide a CLI interface for viewing/editing settings.

**Primary recommendation:** Build `config/config.py` as a lightweight module using Python stdlib only (json + dataclasses + argparse) — no new dependencies. Use a dataclass with `__post_init__` validation for the config schema, and `argparse` with subcommands for the CLI (`python main.py config show/set/reset`).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| json | 3.13 stdlib | Read/write JSON config | Already used in `main.py:load_config()` |
| dataclasses | 3.13 stdlib | Typed config schema with validation | Already used in `models/listing.py`, project pattern |
| argparse | 3.13 stdlib | CLI for viewing/editing settings | stdlib, zero deps, subcommand support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | 3.13 stdlib | Config file path resolution | Already used in `main.py:load_config()` |
| logging | 3.13 stdlib | Config change logging | Already used throughout |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dataclasses + __post_init__ | Pydantic BaseModel | Pydantic adds `pydantic` dependency; dataclasses are stdlib and already in project. Pydantic would give auto-JSON-serialization and richer validation, but overkill for ~10 config fields. |
| argparse | click / typer | Both require `pip install`. argparse is stdlib and sufficient for `config show/set/reset` subcommands. |
| Edit JSON manually | Interactive `input()` prompts | Manual editing is error-prone. CLI `set` subcommand with validation is safer. Keep manual editing as fallback (it's just JSON). |

**Installation:** No new dependencies needed — uses existing stdlib modules.

## Architecture Patterns

### Recommended Project Structure
```
config/
├── config.json        # existing — user-editable settings file
├── config.py          # NEW — ConfigManager class: load, validate, save, defaults
tests/
├── test_config.py     # NEW — unit tests for validation and round-trip persistence
main.py                # modified — use ConfigManager instead of raw load_config()
```

### Pattern 1: Config Dataclass with Validation (dataclasses + __post_init__)
**What:** A `@dataclass` that mirrors the JSON structure, with `__post_init__` for validation. Load from dict, validate on construction, serialize back to dict for saving.
**When to use:** Any settings schema that needs type safety and validation without external deps.
**Example:**
```python
# Source: project pattern from models/listing.py + OneUptime dataclass validation guide (2026-01)
from dataclasses import dataclass, field, asdict
from typing import Optional

VALID_DURATIONS = ["1h", "3h", "6h", "12h", "24h", "3d"]

@dataclass
class BrowserConfig:
    headless: bool = False
    slow_mo: int = 500
    viewport_width: int = 1280
    viewport_height: int = 720

@dataclass
class ListingDefaults:
    duration: str = "3h"
    price_adjustment_type: str = "percentage"   # "percentage" or "fixed"
    price_adjustment_value: float = 0.0
    min_price: int = 200
    max_price: int = 15_000_000

    def __post_init__(self):
        if self.duration not in VALID_DURATIONS:
            raise ValueError(f"duration must be one of {VALID_DURATIONS}, got '{self.duration}'")
        if self.price_adjustment_type not in ("percentage", "fixed"):
            raise ValueError(f"price_adjustment_type must be 'percentage' or 'fixed'")
        if not (200 <= self.min_price <= self.max_price <= 15_000_000):
            raise ValueError(f"Invalid price range: {self.min_price}–{self.max_price}")

@dataclass
class AppConfig:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    listing_defaults: ListingDefaults = field(default_factory=ListingDefaults)
    scan_interval_seconds: int = 60
    rate_limit_min_ms: int = 2000
    rate_limit_max_ms: int = 5000

    def __post_init__(self):
        if not (10 <= self.scan_interval_seconds <= 3600):
            raise ValueError(f"scan_interval_seconds must be 10–3600, got {self.scan_interval_seconds}")
        if self.rate_limit_min_ms > self.rate_limit_max_ms:
            raise ValueError("rate_limit_min_ms must be <= rate_limit_max_ms")
```

### Pattern 2: ConfigManager (Load → Validate → Save)
**What:** A class that wraps config.json I/O, provides typed access, validates on load, and writes back on save. Acts as the single source of truth for config.
**When to use:** Any app that reads/writes a JSON config file.
**Example:**
```python
# Source: existing main.py:load_config() pattern + standard Python I/O
import json
from pathlib import Path
from config.config import AppConfig, BrowserConfig, ListingDefaults

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "config.json"

class ConfigManager:
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH):
        self.path = path
        self._config: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """Load config from JSON, validate, return AppConfig."""
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._config = self._from_dict(raw)
        else:
            self._config = AppConfig()  # defaults
            self.save()                  # create file with defaults
        return self._config

    def save(self) -> None:
        """Serialize current config to JSON file."""
        data = asdict(self._config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def set_value(self, dotted_key: str, value: str) -> None:
        """Set a config value by dotted key (e.g., 'listing_defaults.duration')."""
        # Parse key, cast value, validate via __post_init__, save
        ...

    def reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._config = AppConfig()
        self.save()

    @staticmethod
    def _from_dict(data: dict) -> AppConfig:
        """Convert raw JSON dict to validated AppConfig."""
        browser_data = data.get("browser", {})
        defaults_data = data.get("listing_defaults", {})
        return AppConfig(
            browser=BrowserConfig(**browser_data),
            listing_defaults=ListingDefaults(**defaults_data),
            scan_interval_seconds=data.get("scan_interval_seconds", 60),
            rate_limit_min_ms=data.get("rate_limiting", {}).get("min_delay_ms", 2000),
            rate_limit_max_ms=data.get("rate_limiting", {}).get("max_delay_ms", 5000),
        )
```

### Pattern 3: argparse Subcommands for Config CLI
**What:** Add `config` subcommand to main.py with `show`, `set`, and `reset` sub-subcommands.
**When to use:** Any CLI tool that exposes settings management.
**Example:**
```python
# Source: Python argparse docs + OneUptime CLI guide (2026-02)
import argparse

def build_parser():
    parser = argparse.ArgumentParser(description="FIFA 26 Auto-Relist Tool")
    sub = parser.add_subparsers(dest="command")

    # Run command (default — current behavior)
    run_parser = sub.add_parser("run", help="Run auto-relist")

    # Config command
    config_parser = sub.add_parser("config", help="Manage settings")
    config_sub = config_parser.add_subparsers(dest="config_action")

    show_p = config_sub.add_parser("show", help="Show current settings")
    set_p = config_sub.add_parser("set", help="Set a config value")
    set_p.add_argument("key", help="Dotted key, e.g., listing_defaults.duration")
    set_p.add_argument("value", help="New value")
    reset_p = config_sub.add_parser("reset", help="Reset to defaults")

    return parser
```

### Anti-Patterns to Avoid
- **Direct `config["key"]` access everywhere:** Use typed dataclass so typos and type errors are caught at load time, not at runtime mid-relist.
- **Validation only at save time:** Validate in `__post_init__` so invalid configs are rejected immediately on load, not silently ignored.
- **Hardcoded config paths:** Use `Path(__file__).parent / "config" / "config.json"` so the tool works regardless of working directory.
- **Flattening nested config into flat keys:** Keep the JSON structure matching the dataclass nesting. A "dotted key" CLI interface can still target nested fields (`listing_defaults.duration`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config validation | Custom if/else chains per field | `dataclass.__post_init__` | Centralized, runs on construction, catches bad data early |
| JSON round-trip | Manual dict building per field | `dataclasses.asdict()` | Handles all fields automatically, including nested dataclasses |
| CLI argument parsing | `sys.argv` slicing + manual dispatch | `argparse` subparsers | Auto-generates help, handles errors, standard UX |
| Type coercion from CLI strings | `int(value)`, `float(value)` everywhere | Map field type → cast function | Single coercion function handles all types consistently |

**Key insight:** Python's `dataclasses` + `json` + `argparse` cover all Phase 4 needs without external dependencies. Pydantic/click are better for larger projects but add unnecessary complexity for ~10 config fields.

## Common Pitfalls

### Pitfall 1: Config Format Migration Breaking Existing Users
**What goes wrong:** Changing the config.json structure (e.g., flattening nested dicts) breaks existing installations that have customized settings.
**Why it happens:** The existing `config/config.json` has a specific structure used by `browser/controller.py`, `browser/navigator.py`, and `browser/relist.py` — all reading from the raw dict.
**How to avoid:** Keep the JSON structure backward-compatible. The ConfigManager should read the existing format and map it to the dataclass. Optionally add missing keys with defaults (migration).
**Warning signs:** Existing users report settings reset to defaults after upgrade.

### Pitfall 2: CLI String → Python Type Coercion Errors
**What goes wrong:** User runs `python main.py config set scan_interval_seconds sixty` and gets a confusing TypeError instead of a clear validation error.
**Why it happens:** argparse doesn't know the field types; raw `int("sixty")` throws an unhandled exception.
**How to avoid:** Build a type coercion map keyed by field name. Catch conversion errors and show: "Invalid value for scan_interval_seconds: expected integer, got 'sixty'".
**Warning signs:** Unhandled exceptions when users mistype values.

### Pitfall 3: Config Saved Before Validation
**What goes wrong:** A partially-valid config is written to disk, corrupting the file for next load.
**Why it happens:** Writing the JSON before `__post_init__` validation runs (e.g., if using a mutable dict approach instead of dataclass construction).
**How to avoid:** Always construct the full AppConfig dataclass first (triggers validation), then serialize. Never write partial dicts to the JSON file.
**Warning signs:** App crashes on startup with config validation error after a `config set` command.

### Pitfall 4: Nested Key CLI Parsing Ambiguity
**What goes wrong:** `config set browser.headless true` — the dotted key `browser.headless` needs to map to `AppConfig.browser.headless`.
**Why it happens:** Need to split on `.`, traverse nested dataclass fields, and apply the value.
**How to avoid:** Implement a `set_value(dotted_key, value)` method that splits the key, finds the target field, coerces the value to the correct type, sets it, and validates via dataclass reconstruction.
**Warning signs:** "Key not found" errors for valid nested paths.

## Code Examples

### ConfigManager.load() with Migration
```python
# Source: existing main.py:load_config() + dataclass pattern
def load(self) -> AppConfig:
    if not self.path.exists():
        self._config = AppConfig()
        self.save()
        return self._config

    with open(self.path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Migration: add missing keys with defaults
    defaults = asdict(AppConfig())
    merged = self._deep_merge(defaults, raw)

    self._config = self._from_dict(merged)
    return self._config
```

### asdict() Round-Trip for Save
```python
# Source: Python dataclasses docs
from dataclasses import asdict

def save(self) -> None:
    data = asdict(self._config)
    # Re-nest rate limiting to match existing JSON format
    data["rate_limiting"] = {
        "min_delay_ms": data.pop("rate_limit_min_ms"),
        "max_delay_ms": data.pop("rate_limit_max_ms"),
    }
    with open(self.path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

### CLI Type Coercion
```python
# Type map for CLI value coercion
FIELD_TYPES = {
    "listing_defaults.duration": str,
    "listing_defaults.price_adjustment_type": str,
    "listing_defaults.price_adjustment_value": float,
    "listing_defaults.min_price": int,
    "listing_defaults.max_price": int,
    "scan_interval_seconds": int,
    "rate_limiting.min_delay_ms": int,
    "rate_limiting.max_delay_ms": int,
    "browser.headless": lambda v: v.lower() in ("true", "1", "yes"),
}

def coerce_value(key: str, raw_value: str):
    cast = FIELD_TYPES.get(key)
    if cast is None:
        raise KeyError(f"Unknown config key: {key}")
    try:
        return cast(raw_value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid value for '{key}': expected {cast.__name__}, got '{raw_value}'") from e
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded constants in source | JSON config file | Project created with config.json | User-editable without code changes |
| Raw dict access `config["key"]` | Typed dataclass schema | Phase 4 (this phase) | Validation, IDE autocomplete, type safety |
| `load_config()` in main.py | ConfigManager class | Phase 4 (this phase) | Load + validate + save in one place |
| No CLI for settings | `python main.py config show/set/reset` | Phase 4 (this phase) | Safe, validated user interface |

**Deprecated/outdated:**
- Raw `json.load()` without validation (replace with ConfigManager)
- `config.get("key", default)` scattered across modules (replace with typed access)

## Open Questions

1. **Should Phase 4 also migrate main.py to use ConfigManager?**
   - What we know: `main.py:load_config()` returns a raw dict, consumed by BrowserController, AuthManager, TransferMarketNavigator, RelistExecutor
   - What's unclear: Whether to keep dict-based API (backward compat) or switch all consumers to dataclass access
   - Recommendation: Keep JSON structure compatible with existing dict consumers. ConfigManager provides the typed API for new code and CLI. Existing modules can continue using `config.get()` on the raw dict from `asdict()`.

2. **How should rate_limiting be represented in the dataclass?**
   - What we know: Existing JSON has `rate_limiting: {min_delay_ms, max_delay_ms}` as a nested object
   - What's unclear: Whether to create a RateLimiting dataclass or flatten to top-level fields
   - Recommendation: Create a `RateLimitingConfig` dataclass for clean nesting, but flatten to top-level fields in AppConfig for simpler CLI access. Serialize back to nested format for backward compat.

3. **Should `config set` validate against live config constraints (e.g., min_price <= max_price)?**
   - What we know: Individual field validation is straightforward, but cross-field validation is more complex
   - What's unclear: Whether `__post_init__` handles cross-field validation
   - Recommendation: Yes — `__post_init__` on AppConfig validates cross-field constraints (min_price <= max_price, min_delay <= max_delay). The CLI catches the ValueError and reports it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.0.0 |
| Config file | none (uses defaults) |
| Quick run command | `pytest tests/test_config.py -x --tb=short` |
| Full suite command | `pytest tests/ -x --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONFIG-01 | Listing duration validation (1h, 3h, 6h, 12h, 24h, 3d) | unit | `pytest tests/test_config.py::test_duration_validation -x` | ❌ Wave 0 |
| CONFIG-01 | Invalid duration rejected | unit | `pytest tests/test_config.py::test_invalid_duration -x` | ❌ Wave 0 |
| CONFIG-02 | Price rules min/max/undercut config | unit | `pytest tests/test_config.py::test_price_rules -x` | ❌ Wave 0 |
| CONFIG-02 | Invalid price range rejected (min > max) | unit | `pytest tests/test_config.py::test_invalid_price_range -x` | ❌ Wave 0 |
| CONFIG-03 | Scan interval validation (10–3600s) | unit | `pytest tests/test_config.py::test_scan_interval -x` | ❌ Wave 0 |
| CONFIG-04 | JSON round-trip (load → save → load) | unit | `pytest tests/test_config.py::test_round_trip -x` | ❌ Wave 0 |
| CONFIG-04 | Missing config file creates defaults | unit | `pytest tests/test_config.py::test_create_defaults -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_config.py -x --tb=short`
- **Per wave merge:** `pytest tests/ -x --tb=short`
- **Phase gate:** All tests green + manual CLI smoke test

### Wave 0 Gaps
- [ ] `tests/test_config.py` — unit tests for validation, round-trip, CLI coercion
- [ ] `config/config.py` — AppConfig dataclass + ConfigManager class
- [ ] No new framework install needed (pytest already in requirements.txt)

## Sources

### Primary (HIGH confidence)
- Existing codebase — `config/config.json` structure, `main.py:load_config()`, dataclass pattern in `models/listing.py`
- Python 3.13 dataclasses docs — `@dataclass`, `__post_init__`, `asdict()`, `field(default_factory=...)`
- Python 3.13 json docs — `json.load()`, `json.dump()`, `indent` parameter
- Python 3.13 argparse docs — `add_subparsers()`, subcommand pattern

### Secondary (MEDIUM confidence)
- OneUptime "How to Build Dataclass Validators" (2026-01-30) — `__post_init__` validation, descriptor pattern, when to use Pydantic vs dataclasses
- OneUptime "How to Build CLI Applications with argparse" (2026-02-03) — subcommands, argument groups, environment variable defaults
- Python CLI Tools Guide (2026-01-10) — argparse vs click decision matrix, entry points

### Tertiary (LOW confidence)
- loadcfg library (2025-02) — lightweight JSON config with dot-access (similar goal, but adds dependency)
- dataclass-settings (2025-07) — decoupled settings loading from model definition (overkill for this project)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib, no new deps, already in use
- Architecture: HIGH — follows existing dataclass + JSON patterns from the codebase
- Validation: HIGH — `__post_init__` is well-documented Python feature
- CLI: MEDIUM — argparse subcommands are standard but nesting needs careful design
- Migration: MEDIUM — backward compat with existing dict consumers needs testing

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (30 days — stdlib is stable, config.json structure is already defined)

"""Typed config schema with validation.

Defines AppConfig, BrowserConfig, ListingDefaults, and RateLimitingConfig
as dataclasses with __post_init__ validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_DURATIONS = ["1h", "3h", "6h", "12h", "24h", "3d"]
VALID_RELIST_MODES = ["all", "per_listing"]
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class BrowserConfig:
    """Browser launch configuration."""

    headless: bool = False
    slow_mo: int = 500
    viewport_width: int = 1280
    viewport_height: int = 720


@dataclass
class ListingDefaults:
    """Default listing parameters for relist operations."""

    relist_mode: str = "all"
    duration: str = "1h"
    price_adjustment_type: str = "percentage"
    price_adjustment_value: float = 0.0
    min_price: int = 200
    max_price: int = 15_000_000

    def __post_init__(self):
        if self.relist_mode not in VALID_RELIST_MODES:
            raise ValueError(
                f"relist_mode must be one of {VALID_RELIST_MODES}, got '{self.relist_mode}'"
            )
        if self.duration not in VALID_DURATIONS:
            raise ValueError(
                f"duration must be one of {VALID_DURATIONS}, got '{self.duration}'"
            )
        if self.price_adjustment_type not in ("percentage", "fixed"):
            raise ValueError(
                "price_adjustment_type must be 'percentage' or 'fixed'"
            )
        if not (200 <= self.min_price <= self.max_price <= 15_000_000):
            raise ValueError(
                f"Invalid price range: {self.min_price}–{self.max_price}"
            )


@dataclass
class RateLimitingConfig:
    """Rate limiting delays for anti-detection."""

    min_delay_ms: int = 2000
    max_delay_ms: int = 5000

    def __post_init__(self):
        if self.min_delay_ms > self.max_delay_ms:
            raise ValueError(
                "rate_limiting min_delay_ms must be <= max_delay_ms"
            )


@dataclass
class AppConfig:
    """Root configuration combining all sub-configs."""

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    listing_defaults: ListingDefaults = field(default_factory=ListingDefaults)
    scan_interval_seconds: int = 60
    rate_limiting: RateLimitingConfig = field(default_factory=RateLimitingConfig)

    def __post_init__(self):
        if not (10 <= self.scan_interval_seconds <= 3600):
            raise ValueError(
                f"scan_interval_seconds must be 10–3600, got {self.scan_interval_seconds}"
            )

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Load AppConfig from a dict (parsed from config.json)."""
        browser_data = data.get("browser", {})
        viewport = browser_data.get("viewport", {})
        return cls(
            browser=BrowserConfig(
                headless=browser_data.get("headless", False),
                slow_mo=browser_data.get("slow_mo", 500),
                viewport_width=viewport.get("width", 1280),
                viewport_height=viewport.get("height", 720),
            ),
            listing_defaults=ListingDefaults(**data.get("listing_defaults", {})),
            scan_interval_seconds=data.get("scan_interval_seconds", 60),
            rate_limiting=RateLimitingConfig(**data.get("rate_limiting", {})),
        )

    def to_dict(self) -> dict:
        """Serialize to dict matching config/config.json format."""
        return {
            "browser": {
                "headless": self.browser.headless,
                "slow_mo": self.browser.slow_mo,
                "viewport": {
                    "width": self.browser.viewport_width,
                    "height": self.browser.viewport_height,
                },
            },
            "listing_defaults": {
                "relist_mode": self.listing_defaults.relist_mode,
                "duration": self.listing_defaults.duration,
                "price_adjustment_type": self.listing_defaults.price_adjustment_type,
                "price_adjustment_value": self.listing_defaults.price_adjustment_value,
                "min_price": self.listing_defaults.min_price,
                "max_price": self.listing_defaults.max_price,
            },
            "scan_interval_seconds": self.scan_interval_seconds,
            "rate_limiting": {
                "min_delay_ms": self.rate_limiting.min_delay_ms,
                "max_delay_ms": self.rate_limiting.max_delay_ms,
            },
        }


# --- Field mapping for type coercion ---

_FIELD_CASTS: dict[str, tuple[str, str, type]] = {
    "browser.headless":             ("browser", "headless", bool),
    "browser.slow_mo":              ("browser", "slow_mo", int),
    "browser.viewport_width":       ("browser", "viewport_width", int),
    "browser.viewport_height":      ("browser", "viewport_height", int),
    "listing_defaults.relist_mode":                 ("listing_defaults", "relist_mode", str),
    "listing_defaults.duration":                ("listing_defaults", "duration", str),
    "listing_defaults.price_adjustment_type":   ("listing_defaults", "price_adjustment_type", str),
    "listing_defaults.price_adjustment_value":  ("listing_defaults", "price_adjustment_value", float),
    "listing_defaults.min_price":               ("listing_defaults", "min_price", int),
    "listing_defaults.max_price":               ("listing_defaults", "max_price", int),
    "scan_interval_seconds":        ("", "scan_interval_seconds", int),
    "rate_limiting.min_delay_ms":   ("rate_limiting", "min_delay_ms", int),
    "rate_limiting.max_delay_ms":   ("rate_limiting", "max_delay_ms", int),
}

_TRUE_VALUES = {"true", "1", "yes"}


def _coerce_value(raw: str, target_type: type) -> object:
    """Coerce a CLI string to the target Python type."""
    if target_type is bool:
        return raw.lower() in _TRUE_VALUES
    return target_type(raw)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins)."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# --- ConfigManager ---

class ConfigManager:
    """Manages loading, validating, modifying, and saving AppConfig."""

    def __init__(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        self.path = path
        self._config: AppConfig | None = None
        self._raw: dict = {}

    def load(self) -> AppConfig:
        """Load config from JSON, validate, return AppConfig.

        If the file doesn't exist, create it with defaults.
        Missing keys are filled with defaults (migration).
        """
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self._raw = json.load(f)
            defaults = AppConfig().to_dict()
            merged = _deep_merge(defaults, self._raw)
            self._config = AppConfig.from_dict(merged)
        else:
            self._config = AppConfig()
            self._raw = self._config.to_dict()
            self.save()
        return self._config

    def save(self) -> None:
        """Serialize current config to JSON file."""
        if self._config is None:
            raise RuntimeError("No config loaded — call load() first")
        data = {**self._raw, **self._config.to_dict()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def set_value(self, dotted_key: str, value: str) -> None:
        """Set a config value by dotted key (e.g. 'listing_defaults.duration').

        Validates via AppConfig.__post_init__ after update.
        Unknown keys are stored as raw JSON (preserved across save).
        """
        if self._config is None:
            self.load()

        if dotted_key in _FIELD_CASTS:
            self._set_known_field(dotted_key, value)
        else:
            self._set_unknown_field(dotted_key, value)
        self.save()

    def reset_defaults(self) -> None:
        """Reset all settings to defaults and save."""
        self._config = AppConfig()
        self._raw = self._config.to_dict()
        self.save()

    def _set_known_field(self, dotted_key: str, value: str) -> None:
        """Set a typed field with coercion and validation."""
        section, field_name, target_type = _FIELD_CASTS[dotted_key]
        try:
            coerced = _coerce_value(value, target_type)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid value for '{dotted_key}': "
                f"expected {target_type.__name__}, got '{value}'"
            ) from exc

        old_config = self._config
        data = old_config.to_dict()
        if section:
            data[section][field_name] = coerced
        else:
            data[field_name] = coerced

        try:
            self._config = AppConfig.from_dict(data)
        except ValueError:
            self._config = old_config
            raise

    def _set_unknown_field(self, dotted_key: str, value: str) -> None:
        """Set a non-typed field, stored as raw JSON."""
        parts = dotted_key.split(".")
        node = self._raw
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        try:
            node[parts[-1]] = json.loads(value)
        except json.JSONDecodeError:
            node[parts[-1]] = value

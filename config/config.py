"""Typed config schema with validation.

Defines AppConfig, BrowserConfig, ListingDefaults, and RateLimitingConfig
as dataclasses with __post_init__ validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_DURATIONS = ["1h", "3h", "6h", "12h", "24h", "3d"]
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

    duration: str = "3h"
    price_adjustment_type: str = "percentage"
    price_adjustment_value: float = 0.0
    min_price: int = 200
    max_price: int = 15_000_000

    def __post_init__(self):
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

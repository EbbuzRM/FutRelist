# Testing Patterns

**Analysis Date:** 2026-04-11

## Test Framework

**Runner:** pytest 8.x (detected in test imports)

**Assertion Library:** pytest built-in assertions

**Run Commands:**
```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest tests/        # Run specific directory
pytest tests/test_rate_limiter.py  # Run specific file
```

**Test Discovery:**
- Files: `tests/test_*.py`, `tests/*_test.py`
- Classes: `Test*`
- Functions: `test_*`

## Test File Organization

**Location:** `tests/` directory (co-located, not separate)

**Structure:**
```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_rate_limiter.py
├── test_config.py
├── test_detector.py
├── test_bot_state.py
├── test_action_log.py
├── test_telegram_handler.py
├── test_sold_handler.py
├── test_error_handler.py
├── test_relist.py
└── test_listing_model.py
```

**Naming:** `test_<module_name>.py`

## Test Structure

**Class Organization:**
```python
class TestRateLimiter:
    """Test RateLimiter delay enforcement."""

    def test_init_with_defaults(self):
        """RateLimiter init with defaults from RateLimitingConfig (2000, 5000)."""
        limiter = RateLimiter()
        assert limiter.min_delay_ms == 2000
        assert limiter.max_delay_ms == 5000
```

**Test Naming:** `test_<what_is_tested>`

**Docstrings:** One-line description of what is being tested

**Assertions:** Clear, single-purpose tests

## Fixtures (conftest.py)

**Location:** `tests/conftest.py`

**Provided Fixtures:**
```python
@pytest.fixture
def sample_listing_html():
    """Returns mock HTML matching WebApp DOM structure with 3 player listings."""
    return """
    <div class="listFUTItem player">
        <div class="player-name">Mbappé</div>
        <div class="rating">91</div>
        ...
    </div>
    """

@pytest.fixture
def empty_listings_html():
    """Returns HTML with no listing items (empty state)."""
    return '<div class="no-items"></div>'
```

## Mocking Patterns

**Monkeypatch:**
```python
def test_wait_sleeps(self, monkeypatch):
    """wait() sleeps for a delay within the configured range."""
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    limiter = RateLimiter(min_delay_ms=1000, max_delay_ms=1000)
    limiter.wait()

    assert len(sleeps) == 1
    assert 0.9 <= sleeps[0] <= 1.1  # ~1000ms
```

**Key Points:**
- Mock `time.sleep` for timing tests
- Use `monkeypatch.setattr()` to intercept calls
- Assertions on mocked values

## Class-Based Testing

**Test Classes Group Related Tests:**
```python
class TestListingDefaults:
    """Tests for ListingDefaults duration, price rules, and adjustment validation."""

    def test_duration_valid(self):
        """Valid durations are accepted."""
        for duration in VALID_DURATIONS:
            listing = ListingDefaults(duration=duration)
            assert listing.duration == duration
```

## Coverage Areas

**Config Tests:**
- `tests/test_config.py` (165 lines)
- Validation: duration, price range, relist_mode
- JSON round-trip serialization
- BrowserConfig defaults
- Rate limiting config

**Rate Limiter Tests:**
- `tests/test_rate_limiter.py` (46 lines)
- Init with defaults
- Init with custom values
- `wait()` timing enforcement

**Detector Tests:**
- `tests/test_detector.py` (105 lines)
- `parse_price()` function
- `parse_rating()` function
- `determine_state()` - English/Italian localization

**Bot State Tests:**
- `tests/test_bot_state.py` (217 lines)
- Initialization
- Pause/resume
- Force relist flag (consume-on-read)
- Stats updates
- Thread safety with concurrent access

**Action Log Tests:**
- `tests/test_action_log.py`
- JSON serialization
- Parse history

## Thread Safety Testing

**Pattern in test_bot_state.py:**
```python
class TestBotStateThreadSafety:
    """Test per thread safety con accesso concorrente."""

    def test_concurrent_set_paused(self):
        """100 thread concorrenti non corrompono lo stato."""
        state = BotState()
        errors = []

        def toggle(n: int):
            try:
                state.set_paused(n % 2 == 0)
                _ = state.is_paused()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=toggle, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
```

**Key Points:**
- Create 100 threads for stress testing
- Check for no exceptions raised
- Verify final state is consistent

## Test Patterns

**Validation Tests:**
```python
def test_duration_invalid(self):
    """Invalid duration raises ValueError."""
    with pytest.raises(ValueError, match="duration"):
        ListingDefaults(duration="2h")
```

**Input/Output Tests:**
```python
def test_round_trip(self):
    """AppConfig survives to_dict → JSON → from_dict round-trip."""
    original = AppConfig(...)
    json_str = json.dumps(original.to_dict())
    loaded = AppConfig.from_dict(json.loads(json_str))
    assert loaded == original
```

**Edge Cases:**
```python
def test_parse_price_none(self):
    """parse_price(None) is None"""
    from browser.detector import parse_price
    assert parse_price(None) is None
```

## Key Test Files

**Config Tests (`tests/test_config.py`):**
- ListingDefaults validation
- AppConfig scan intervals
- Rate limiting valid ranges
- JSON round-trip

**Bot State Tests (`tests/test_bot_state.py`):**
- Thread-safe state management
- Pause/resume/force relist flags
- Stats accumulation

**Detector Tests (`tests/test_detector.py`):**
- Price parsing (formatted, plain, None)
- Rating parsing (with prefix)
- State determination (EN/IT)

## Anti-Patterns to Avoid

1. **No browser automation in unit tests** - Mock the page/selectors
2. **No external API calls** - Use fixtures for HTML samples
3. **No sleep-dependent timing** - Monkeypatch time.sleep

---

*Testing analysis: 2026-04-11*
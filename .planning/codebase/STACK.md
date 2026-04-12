# Technology Stack

**Analysis Date:** 2026-04-11

## Languages

**Primary:**
- Python 3.9+ - Main scripting language for automation

**Secondary:**
- None detected - Pure Python project

## Runtime

**Environment:**
- Python 3.9+ (standard CPython)
- Platform: Windows/macOS/Linux compatible

**Package Manager:**
- pip (standard)
- requirements.txt is directly used: `pip install -r requirements.txt`
- Lockfile: Not present

## Frameworks

**Core:**
- Playwright >=1.40.0 - Browser automation for FIFA WebApp interaction
- python-dotenv >=1.0.0 - Environment variable loading from `.env` file

**Testing:**
- pytest >=7.0.0 - Unit testing framework

**Build/Dev:**
- tenacity >=8.0 - Retry logic for transient failures
- rich >=13.0 - Terminal UI with tables and formatting

## Key Dependencies

**Critical:**
- playwright >=1.40.0 - Core browser automation (EA WebApp interaction)
- python-dotenv >=1.0.0 - Credentials loading from `.env`

**Infrastructure:**
- tenacity >=8.0 - Retry decorator for API calls
- rich >=13.0 - Console output formatting

**Testing:**
- pytest >=7.0.0 - Test framework

## Configuration

**Environment:**
- `.env` file for credentials (FIFA_EMAIL, FIFA_PASSWORD)
- `config/config.json` for application settings
- Template: `.env.example` and `config/config.example.json`

**Build:**
- `setup.py` - Interactive setup script
- `requirements.txt` - Direct dependencies
- No pyproject.toml or setup.cfg detected

**Key settings in config/config.json:**
```json
{
  "browser": { "headless": false, "slow_mo": 500 },
  "listing_defaults": {
    "relist_mode": "all",
    "duration": "1h",
    "price_adjustment_type": "percentage",
    "price_adjustment_value": 0.0,
    "min_price": 200,
    "max_price": 15000000
  },
  "scan_interval_seconds": 3600,
  "rate_limiting": { "min_delay_ms": 2000, "max_delay_ms": 5000 }
}
```

## Platform Requirements

**Development:**
- Python 3.9+
- Playwright browsers installed (`playwright install`)

**Production:**
- Persistent browser profile in `storage/browser_profile`
- Session cookies saved for re-authentication

---

*Stack analysis: 2026-04-11*
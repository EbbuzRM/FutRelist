# FIFA 26 Auto-Relist Tool — Codebase Map

**Analysis Date:** 2026-03-23
**Project Root:** `C:\App\fifa-relist`
**Language:** Python 3.13
**Current Phase:** Phase 1 complete (Browser Setup & Authentication)

---

## Directory Tree

```
fifa-relist/
├── main.py                 # Entry point — orchestrator
├── requirements.txt        # Python dependencies
├── config/
│   └── config.json         # App configuration (browser, auth, listing defaults)
├── browser/
│   ├── __init__.py         # Empty package marker
│   ├── controller.py       # Playwright browser lifecycle management
│   └── auth.py             # Login flow + session persistence
├── storage/                # Runtime-generated; stores session state
│   ├── cookies.json        # (created at runtime)
│   └── browser_state.json  # (created at runtime)
├── logs/
│   └── app.log             # Application log output
└── .planning/              # GSD project management (not part of app)
    ├── PROJECT.md
    ├── REQUIREMENTS.md
    ├── ROADMAP.md
    ├── STATE.md
    ├── MILESTONES.md
    ├── LOG.md
    └── phases/
        └── 01-browser-setup/
            ├── 01-project-setup-PLAN.md / SUMMARY.md
            ├── 02-browser-controller-PLAN.md / SUMMARY.md
            └── 03-auth-session-PLAN.md / SUMMARY.md
```

---

## Module Map

### `main.py` — Entry Point / Orchestrator

| Aspect | Detail |
|--------|--------|
| **Path** | `main.py` |
| **Responsability** | Application bootstrap, config loading, credential retrieval, orchestration of browser + auth |
| **Imports from project** | `browser.controller.BrowserController`, `browser.auth.AuthManager` |
| **External imports** | `json`, `logging`, `os`, `sys`, `pathlib.Path` |
| **Key functions** | `setup_logging()` — configura file + console logging; `load_config()` — legge `config/config.json`; `get_credentials()` — da env vars o input utente; `main()` — entry point principale |
| **Flow** | Setup logging → load config → create BrowserController → create AuthManager → start browser → navigate to WebApp → attempt session restore → fallback to manual login → save session → wait for user input → stop browser |
| **Connected to** | `browser/controller.py` (lifecycle browser), `browser/auth.py` (autenticazione), `config/config.json` (configurazione) |

### `browser/controller.py` — BrowserController

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/controller.py` |
| **Responsability** | Wrapper Playwright per lancio/chiusura browser, navigazione alla WebApp |
| **Class** | `BrowserController` |
| **External imports** | `playwright.sync_api` (`sync_playwright`, `Browser`, `BrowserContext`, `Page`) |
| **State** | `self.playwright`, `self.browser`, `self.context`, `self.page`, `self._is_running` |
| **Key methods** | `start() -> Page` — lancia Chromium con config da `config.json`; `navigate_to_webapp()` — goto FIFA WebApp URL con `networkidle`; `get_page() -> Page`; `stop()` — chiude context → browser → playwright (ordine inverso); `is_running() -> bool`; `__enter__`/`__exit__` — context manager support |
| **Config consumed** | `config["browser"]["headless"]`, `config["browser"]["slow_mo"]`, `config["browser"]["viewport"]`, `config["fifa_webapp_url"]` |
| **Connected to** | `main.py` (chiamante), `browser/auth.py` (usa `self.context` per session persistence) |

### `browser/auth.py` — AuthManager

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/auth.py` |
| **Responsability** | Login su FIFA WebApp, rilevamento stato login, persistenza sessione (cookies + browser state) |
| **Class** | `AuthManager` |
| **External imports** | `json`, `logging`, `pathlib.Path`, `playwright.sync_api.Page` |
| **Constants** | `SELECTORS` dict — CSS selectors per: login_button, email_input, password_input, submit_button, main_page, transfer_market, my_listings, webapp_home |
| **State** | `self.storage_dir` (`storage/`), `self.cookies_file` (`storage/cookies.json`), `self.state_file` (`storage/browser_state.json`) |
| **Key methods** | `has_saved_session() -> bool` — check se files esistono; `load_session(context)` — carica state JSON nel context Playwright; `save_session(context)` — salva `storage_state()` su disco; `is_logged_in(page) -> bool` — detection via selector `.ut-app` o URL check; `wait_for_login_page(page) -> bool` — attesa selector login; `perform_login(page, email, password) -> bool` — fill email → fill password → submit; `delete_saved_session()` — cancella files |
| **Runtime files** | `storage/cookies.json`, `storage/browser_state.json` |
| **Connected to** | `main.py` (chiamante), `browser/controller.py` (riceve `controller.context` per session ops) |

### `config/config.json` — Configuration

| Aspect | Detail |
|--------|--------|
| **Path** | `config/config.json` |
| **Responsability** | Configurazione centralizzata dell'applicazione |
| **Keys** | `fifa_webapp_url` — URL WebApp; `browser.headless` — false (modalità visibile); `browser.slow_mo` — 500ms delay tra azioni; `browser.viewport` — 1280x720; `auth.save_session` — true; `auth.session_timeout_hours` — 24h; `auth.use_env_credentials` — true; `scan_interval_seconds` — 60s (non ancora usato); `listing_defaults` — duration/price rules (non ancora usati); `rate_limiting` — min/max delay ms (non ancora usati) |
| **Consumed by** | `main.py` (load_config), `browser/controller.py` (start, navigate_to_webapp), `browser/auth.py` (config reference) |

### `browser/__init__.py` — Package Marker

| Aspect | Detail |
|--------|--------|
| **Path** | `browser/__init__.py` |
| **Responsability** | Marca `browser/` come package Python |
| **Content** | Vuoto (0 righe) |

---

## Data Flow — Main Execution Path

```
main.py::main()
  │
  ├─ setup_logging()          → logs/app.log + console
  ├─ load_config()            ← config/config.json
  ├─ get_credentials()        ← env vars (FIFA_EMAIL, FIFA_PASSWORD) or stdin
  │
  ├─ BrowserController(config)
  │   └─ .start()             → Playwright → Chromium → BrowserContext → Page
  │
  ├─ AuthManager(config)
  │
  ├─ controller.navigate_to_webapp()  → page.goto(FIFA URL)
  │
  ├─ auth.has_saved_session()?
  │   ├─ YES → auth.load_session(context) → page.reload()
  │   └─ NO  → (skip)
  │
  ├─ auth.is_logged_in(page)?
  │   ├─ YES → "Già loggato"
  │   └─ NO  → auth.wait_for_login_page(page)
  │              → get_credentials()
  │              → auth.perform_login(page, email, password)
  │              → auth.save_session(context)
  │
  └─ controller.stop()        ← user presses ENTER
      └─ context.close() → browser.close() → playwright.stop()
```

---

## External Dependencies

From `requirements.txt`:

| Package | Version | Purpose |
|---------|---------|---------|
| `playwright` | >= 1.40.0 | Browser automation (Chromium control, selectors, navigation) |
| `python-dotenv` | >= 1.0.0 | .env file loading (declared but not yet imported in code) |

**Note:** `python-dotenv` is listed in requirements but NOT used in any source file. Credentials are read via `os.environ.get()` directly, not through dotenv.

---

## Architecture Notes

### Pattern
**Procedural orchestration** — `main.py` is a flat script with functions, not a class-based architecture. `BrowserController` and `AuthManager` are the only classes.

### Layer Structure
```
┌─────────────────────────────┐
│  main.py (Orchestrator)     │  ← entry point, config, credentials
├─────────────────────────────┤
│  browser/controller.py      │  ← Playwright lifecycle (launch/close/navigate)
│  browser/auth.py            │  ← Login flow + session persistence
├─────────────────────────────┤
│  config/config.json         │  ← static configuration
│  storage/*.json             │  ← runtime session state
└─────────────────────────────┘
```

### What's Implemented (Phase 1)
- ✅ Playwright browser launch with configurable headless/viewport/slow_mo
- ✅ Navigation to FIFA WebApp URL
- ✅ Login detection (selector-based + URL-based)
- ✅ Login automation (email/password fill + submit)
- ✅ Session persistence (save/load cookies + browser state to JSON)
- ✅ Credential input from env vars or interactive prompt

### What's NOT Yet Implemented (Phases 2–5)
- ❌ Transfer Market navigation (BROWSER-04)
- ❌ Listing detection — expired vs active (DETECT-01..04)
- ❌ Auto-relist actions (RELIST-01..04)
- ❌ Price adjustment logic (CONFIG-02)
- ❌ Continuous scan loop (CONFIG-03, uses `scan_interval_seconds` from config)
- ❌ Action logging with timestamps (LOG-01..04)
- ❌ Error recovery — network, session expiration, UI changes (ERROR-01..04)
- ❌ Rate limiting enforcement (rate_limiting in config but unused)

### Key Selectors (in `browser/auth.py`)
The `SELECTORS` dict contains CSS selectors for FIFA WebApp elements. Some (like `transfer_market`, `my_listings`) are defined but not yet used — they are prepared for Phase 2.

### Configuration Fields Unused
Several config fields exist in `config.json` but have no consuming code yet:
- `scan_interval_seconds` (60) — for the future polling loop
- `listing_defaults.duration` / `price_adjustment_type` / `price_adjustment_value`
- `rate_limiting.min_delay_ms` / `max_delay_ms`

---

## Risks & Observations

1. **`python-dotenv` unused** — declared in requirements.txt but never imported. Either remove it or add `from dotenv import load_dotenv` to `main.py` for .env support.

2. **Hardcoded relative paths** — `AuthManager` uses `Path("storage/")` (relative to CWD), while `main.py` uses `Path(__file__).parent / "logs"`. Inconsistent path resolution — could break if CWD ≠ project root.

3. **No error granularity** — `perform_login()` returns `False` on any exception but doesn't distinguish between "element not found" vs "network error" vs "2FA required".

4. **Session state assignment** — `load_session()` does `context.storage_state = state` (attribute assignment), but Playwright's `BrowserContext` may expect `storage_state` to be set at creation time via `new_context(storage_state=...)`, not mutated after. This could silently fail.

5. **No continuous loop yet** — `main.py` currently runs once and waits for ENTER. The `scan_interval_seconds` config implies a future polling loop that doesn't exist.

---

*Codebase map: 2026-03-23 — Phase 1 complete, 4 source files, ~340 lines of application code.*

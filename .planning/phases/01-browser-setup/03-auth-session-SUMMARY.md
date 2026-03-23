# Plan 03-auth-session - SUMMARY

**Piano:** 03-auth-session
**Fase:** 01 - Browser Setup
**Data:** 2026-03-23
**Stato:** COMPLETATO

## Obiettivo
Implementare autenticazione a FIFA 26 WebApp con gestione cookie persistente tra sessioni.

## Requisiti coperti
- BROWSER-02: Autenticarsi con credenziali FIFA 26 (salvate in modo sicuro)
- BROWSER-03: Mantenere cookie di sessione tra i riavvii

## Task completati

### Task 1: `fifa-relist/browser/auth.py`
- **File creato:** `fifa-relist/browser/auth.py`
- Dict `SELECTORS` con CSS selectors per login, email, password, submit, home page
- Classe `AuthManager` con tutti i metodi richiesti:
  - `__init__(config)` - Crea storage_dir, cookies_file, state_file
  - `has_saved_session()` - Verifica esistenza file cookie e state
  - `load_session(context)` - Carica JSON state nel BrowserContext
  - `save_session(context)` - Salva storage_state() su JSON
  - `is_logged_in(page)` - Verifica presenza elementi home o URL
  - `wait_for_login_page(page, timeout)` - Aspetta selettore login
  - `perform_login(page, email, password)` - Click login, fill credenziali, submit
  - `delete_saved_session()` - Elimina file sessione

### Task 2: `fifa-relist/main.py`
- **File aggiornato:** `fifa-relist/main.py`
- Import di `BrowserController` e `AuthManager`
- Funzione `get_credentials()` per env vars (FIFA_EMAIL/FIFA_PASSWORD) o input utente
- `main()` integra AuthManager:
  - Se sessione salvata: load e reload pagina
  - Se non loggato: wait login page, get credentials, perform login, save session
  - Gestione errori e cleanup corretto

### Task 3: `fifa-relist/config/config.json`
- **File aggiornato:** `fifa-relist/config/config.json`
- Sezione `auth` aggiunta:
  - `save_session`: true
  - `session_timeout_hours`: 24
  - `use_env_credentials`: true

## File creati/modificati
| File | Azione |
|------|--------|
| `fifa-relist/browser/auth.py` | Creato |
| `fifa-relist/main.py` | Aggiornato |
| `fifa-relist/config/config.json` | Aggiornato |

## Note
- LSP errors su `playwright.sync_api` sono attesi: playwright non installato nell'ambiente corrente. L'import funzionerà a runtime dopo `pip install playwright`.
- La sessione viene salvata in `storage/browser_state.json` e `storage/cookies.json`.
- Le credenziali possono essere fornite via env vars `FIFA_EMAIL` e `FIFA_PASSWORD` o tramite input interattivo.

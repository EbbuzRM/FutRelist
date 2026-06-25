## 2026-05-20 — Prima inizializzazione SESSIONS.md

### Task completati
- Creato SESSIONS.md (allineamento con Regola 10 conductor-rules)
- Creata struttura iniziale del file di sessione

### Decisioni prese
- SESSIONS.md sarà letto all'avvio di ogni sessione come da Regola 10
- Il file segue il formato: DATA, Task completati, File modificati, Decisioni prese, Issue aperte

## 2026-05-22 — Riscrittura README, review e fix setup scripts

### Task completati
- Riscritto README.md con struttura moderna (badge, pitch, quick start, golden hours, telegram, architettura, license) seguendo GitHub best practices 2026
- Aggiunta sezione Quick Start con setup automatico (setup.bat/setup.sh) e manuale
- Code review completa di setup.py, setup.bat, setup.sh (8 finding)
- Fixati tutti i finding:
  - H-01: Allineati default rate limiting a 1200/2800 su setup.py, config.py, config.example.json, README
  - M-01: Protezione .env cross-platform (icacls Windows + chmod Unix)
  - M-02: playwright install → playwright install chromium (solo Chromium)
  - M-03: .env ora include TELEGRAM_TOKEN e TELEGRAM_CHAT_ID
  - M-04: Aggiunto check presenza Python in setup.bat e setup.sh
  - L-01: Validazione input email/password obbligatori in setup.py
  - L-02: Aggiunti max_price e scan_interval_seconds alla tabella Config del README
  - Minore: rimosso import sys ridondante in setup.py
- Aggiunta guida Telegram (@BotFather, @userinfobot) nei prompt di setup.py e come commento in setup.bat e setup.sh

### File modificati
- README.md (riscritto completamente: 102 → 248 righe)
- setup.py (5 fix: playwright chromium, .env arricchito, input validation, chmod cross-platform, guida Telegram)
- setup.bat (check Python + commento Telegram)
- setup.sh (check Python + commento Telegram)
- config/config.py (default rate limiting 1200/2800)
- config/config.example.json (default rate limiting 1200/2800)

### Decisioni prese
- Default rate limiting fissato a 1200/2800 (profilo Bilanciato) — allineato tra README, codice e setup automatico
- setup.py come punto unico di setup interattivo; setup.bat/setup.sh sono thin launcher
- .env protetto con icacls su Windows e chmod 600 su Unix per sicurezza credenziali

## 2026-05-25 - Menu probe sessione WebApp

### Task completati
- Implementato `AuthManager.probe_session_alive()` come controllo attivo della sessione: cambio menu `Home/Casa/Club -> Transfers`, controllo modali di logout, console session e URL login.
- Collegato il menu probe a heartbeat e recovery sessione: `SessionKeeper._execute_heartbeat()` e `ensure_session()` non si fidano piu solo della shell WebApp visibile.
- Aggiunto fallback a refresh completo dopo fallimenti consecutivi del menu probe.
- Aggiunti test di regressione per probe, fallback refresh, heartbeat e `ensure_session()`.

### File modificati
- `browser/auth.py`
- `browser/session_keeper.py`
- `browser/error_handler.py`
- `tests/test_auth_probe.py`
- `tests/test_session_keeper.py`
- `tests/test_error_handler.py`

### Decisioni prese
- Strategia primaria: menu probe, perche l'osservazione reale e che EA mostra il logout quando si cambia menu.
- Fallback refresh solo in casi estremi: default dopo 3 probe non conclusivi (`session_probe_refresh_after_failures`).
- Un probe non conclusivo rende la sessione incerta e avvia recovery, evitando falsi positivi da `is_logged_in()`.

### Verifica
- `python -m pytest` -> 746 test passano.
- `python -m ruff` non eseguito: modulo `ruff` non installato nell'ambiente corrente.

## 2026-05-28 - Supporto Nuovo Metodo Accesso EA (Remember Me)

### Task completati
- Modificato `AuthManager.perform_login()` in `browser/auth.py` per rilevare dinamicamente la nuova schermata EA con utente memorizzato (Remember Me).
- Implementata logica per verificare se l'utente pre-selezionato corrisponde a quello configurato in `.env`.
- Caso coincidente: inserimento diretto della password e click su Sign in, bypassando il flusso email.
- Caso non coincidente: click automatico sul link di cambio utente per ricadere nel flusso di login classico.

### File modificati
- `browser/auth.py`

### Decisioni prese
- Sfruttare il profilo "Remember Me" per un login più rapido ed esente da errori quando l'utente corrisponde.
- Utilizzare i selettori testuali su body per la verifica flessibile dell'utente pre-selezionato (supporto parziale o totale dell'email).
